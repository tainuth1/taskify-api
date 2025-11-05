from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.config import settings
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectDetailResponse, ProjectUpdate
from app.schemas.user import User as UserSchema
from app.models import Project as ProjectModel, ProjectMember, User
from app.models.project import ProjectType as ProjectTypeModel
from app.models.project_member import MemberRole, MemberStatus


class ProjectController:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, project_data: ProjectCreate, token: str) -> ProjectResponse:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")
        
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        
        user_id = payload.get("sub")
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        if not user.is_active:
            raise ValueError("User is inactive")
        
        # Convert schema ProjectType to model ProjectType
        project_type = ProjectTypeModel.personal
        if project_data.type.value == "group":
            project_type = ProjectTypeModel.group
        
        # Create new project
        new_project = ProjectModel(
            name=project_data.name,
            description=project_data.description,
            owner_id=user_id,
            type=project_type
        )
        
        self.db.add(new_project)
        self.db.flush()  # Flush to get the project ID
        
        # Create project member entry with owner role
        project_member = ProjectMember(
            user_id=user_id,
            project_id=new_project.id,
            role=MemberRole.owner,
            status=MemberStatus.active
        )
        
        self.db.add(project_member)
        self.db.commit()
        self.db.refresh(new_project)

        owner_schema = UserSchema.model_validate(user)
        project_response = ProjectResponse(
            id=new_project.id,
            name=new_project.name,
            description=new_project.description,
            type=project_data.type,
            owner_id=new_project.owner_id,
            members=[{"user": owner_schema, "role": "owner"}],
            created_at=new_project.created_at,
            updated_at=new_project.updated_at,
        )

        return project_response

    # Hellper method
    def _check_project_access(self, user_id: str, project_id: str) -> bool:
        """Check if user has access to a project.
        
        For personal projects: user must be owner
        For group projects: user must be active member
        """
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            return False
        
        member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id)
            .filter(ProjectMember.user_id == user_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        
        # Personal projects: must be owner
        if project.type == ProjectTypeModel.personal:
            return member is not None and member.role == MemberRole.owner
        # Group projects: must be active member
        else:
            return member is not None

    # Hellper method
    def _get_user_project_role(self, user_id: str, project_id: str) -> MemberRole | None:
        """Get user's role in a project, or None if no access."""
        member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id)
            .filter(ProjectMember.user_id == user_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        return member.role if member else None

    def get_all_projects(self, token: str) -> list[ProjectResponse]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")
        
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")

        # Join projects with project_members to find all projects for this user (active membership)
        # Personal projects: only show if user is owner
        # Group projects: show if user is any active member
        # return personal project when user is owner
        # and return group project when user is an active members
        projects = (
            self.db.query(ProjectModel)
            .join(ProjectMember, ProjectMember.project_id == ProjectModel.id)
            .filter(ProjectMember.user_id == user_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .filter(
                or_(
                    # Personal: must be owner
                    and_(
                        ProjectModel.type == ProjectTypeModel.personal,
                        ProjectMember.role == MemberRole.owner
                    ),
                    # Group: any active member
                    ProjectModel.type == ProjectTypeModel.group
                )
            )
            .all()
        )

        if not projects:
            return []

        # Fetch all members for these projects in bulk to get all members for all projects
        project_ids = {p.id for p in projects}
        member_rows = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id.in_(project_ids))
            .all()
        )

        # Load all users referenced by members
        user_ids = {str(m.user_id) for m in member_rows}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {str(u.id): u for u in users}

        # Group members per project
        members_by_project: dict[str, list[dict]] = {}
        for m in member_rows:
            u = user_map.get(str(m.user_id))
            if not u:
                continue
            entry = {"user": UserSchema.model_validate(u), "role": m.role.value}
            members_by_project.setdefault(str(m.project_id), []).append(entry)

        responses: list[ProjectResponse] = []
        for p in projects:
            members_payload = members_by_project.get(str(p.id), [])
            project_schema = ProjectResponse.model_validate(p)
            project_schema = project_schema.model_copy(update={"members": members_payload})
            responses.append(project_schema)

        return responses

    def get_project_by_id(self, token: str, project_id: str) -> ProjectDetailResponse:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")
        
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")
        
        # Check if project exists
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check access
        if not self._check_project_access(user_id, project_id):
            raise ValueError("Access denied")
        
        # Get user's role in the project
        user_role = self._get_user_project_role(user_id, project_id)
        
        # Fetch all members for this project
        member_rows = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .all()
        )
        
        # Load all users referenced by members
        user_ids = {str(m.user_id) for m in member_rows}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {str(u.id): u for u in users}
        
        # Build members list
        members_payload: list[dict] = []
        for m in member_rows:
            u = user_map.get(str(m.user_id))
            if not u:
                continue
            entry = {"user": UserSchema.model_validate(u), "role": m.role.value}
            members_payload.append(entry)
        
        # Convert project type enum for schema
        from app.schemas.project import ProjectType as ProjectTypeSchema
        project_type = ProjectTypeSchema.personal if project.type == ProjectTypeModel.personal else ProjectTypeSchema.group
        
        # Build response
        project_detail = ProjectDetailResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            type=project_type,
            owner_id=project.owner_id,
            members=members_payload,
            user_role=user_role.value if user_role else None,
            tasks=[],  # Empty for now, structure for future
            subtasks=[],  # Empty for now, structure for future
            comments=[],  # Empty for now, structure for future
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        
        return project_detail

    def update_project(self, updated_project: ProjectUpdate, token: str)-> ProjectResponse:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        
        user_id = payload.get("sub")

        project = self.db.query(ProjectModel).filter(ProjectModel.id == updated_project.id).first()
        if not project:
            raise ValueError("Project not found")

        # Get user's role in the project
        user_role = self._get_user_project_role(user_id, str(updated_project.id))
        # Check if user has permission (owner or admin only)
        if not user_role or user_role not in [MemberRole.owner, MemberRole.admin]:
            raise ValueError("Only owners and admins can update projects")

        # Update only provided fields
        if updated_project.name is not None:
            project.name = updated_project.name
        
        if updated_project.description is not None:
            project.description = updated_project.description

        # Enable if allow to update project type: Not Recommanded
        # if updated_project.type is not None:
        #     project_type = ProjectTypeModel.personal
        #     if updated_project.type.value == "group":
        #         project_type = ProjectTypeModel.group
        #     project.type = project_type

        self.db.commit()
        self.db.refresh(project)

        # Fetch all members for this project
        member_rows = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.id)
            .filter(ProjectMember.status == MemberStatus.active)
            .all()
        )
        
        # Load all users referenced by members
        user_ids = {str(m.user_id) for m in member_rows}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {str(u.id): u for u in users}
        
        # Build members list
        members_payload: list[dict] = []
        for m in member_rows:
            u = user_map.get(str(m.user_id))
            if not u:
                continue
            entry = {"user": UserSchema.model_validate(u), "role": m.role.value}
            members_payload.append(entry)
        
        # Convert project type enum for schema
        from app.schemas.project import ProjectType as ProjectTypeSchema
        project_type = ProjectTypeSchema.personal if project.type == ProjectTypeModel.personal else ProjectTypeSchema.group
        
        # Build response
        project_response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            type=project_type,
            owner_id=project.owner_id,
            members=members_payload,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        
        return project_response

    def delete_project(self, token: str, project_id: str) -> dict:
        """Delete a project. Only the owner can delete it.
        
        Raises ValueError if project not found, access denied, or insufficient permissions.
        Returns a success message with project details before deletion.
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")
        
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Verify user is the owner (only owner can delete)
        if str(project.owner_id) != user_id:
            raise ValueError("Only the project owner can delete the project")
        
        # Double-check: Verify user has owner role in project_members table
        # This ensures consistency between project.owner_id and project_members
        user_role = self._get_user_project_role(user_id, project_id)
        if not user_role or user_role != MemberRole.owner:
            raise ValueError("Only the project owner can delete the project")
        
        # Store project info for response before deletion
        project_info = {
            "id": str(project.id),
            "name": project.name,
            "type": project.type.value if hasattr(project.type, 'value') else str(project.type)
        }
        
        # Delete the project (CASCADE will handle project_members, tasks, etc.)
        self.db.delete(project)
        self.db.commit()
        
        return {
            "message": "Project deleted successfully",
            "deleted_project": project_info
        }