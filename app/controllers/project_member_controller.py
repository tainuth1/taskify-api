from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone

from app.core.config import settings
from app.models import ProjectMember, User, Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.schemas.project_member import MemberRoleUpdate, ProjectMemberResponse, ProjectMemberDetailResponse
from app.schemas.user import User as UserSchema
from app.controllers.project_controller import ProjectTypeModel
from app.schemas.project_member import MemberRemoveRequest
from pydantic import BaseModel
import uuid

class ProjectMemberController:
    def __init__(self, db: Session):
        self.db = db

    def _authenticate_user(self, token: str) -> str:
        """Extract and validate user from token. Returns user_id."""
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
        
        return user_id

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
    
    def get_project_members(self, token: str, project_id: str) -> list[ProjectMemberDetailResponse]:
        """Get all active members of a project.
        
        Only project members (any role) can access this endpoint.
        """
        user_id = self._authenticate_user(token)
        
        # Verify project exists
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check if user is a member of the project (any role)
        requester_role = self._get_user_project_role(user_id, project_id)
        if not requester_role:
            raise ValueError("Access denied: You are not a member of this project")
        
        # Get all active members for this project
        member_rows = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .all()
        )
        
        if not member_rows:
            return []
        
        # Load all users referenced by members
        user_ids = {str(m.user_id) for m in member_rows}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {str(u.id): u for u in users}
        
        # Build response list
        members_response = []
        for m in member_rows:
            u = user_map.get(str(m.user_id))
            if not u:
                continue
            
            member_detail = ProjectMemberDetailResponse(
                id=m.id,
                user=UserSchema.model_validate(u),
                role=m.role.value,
                status=m.status.value,
                join_at=m.join_at,
                left_at=m.left_at
            )
            members_response.append(member_detail)
        
        return members_response

    def update_member_role(self, payload: MemberRoleUpdate, token: str) -> ProjectMemberResponse:
        """Update a member's role in a project.
        
        Rules:
        - Owner can change member role to admin/member/viewer, but cannot assign owner role
        - Admin can change member role to member/viewer, but cannot assign admin or owner roles
        - Member and viewer cannot change roles
        """
        user_id = self._authenticate_user(token)
        
        # Verify project exists
        project = self.db.query(ProjectModel).filter(ProjectModel.id == str(payload.project_id)).first()
        if not project:
            raise ValueError("Project not found")
        
        # Get the requester's role in the project
        requester_role = self._get_user_project_role(user_id, str(payload.project_id))
        if not requester_role:
            raise ValueError("Access denied: You are not a member of this project")
        
        # Check permissions: Only owner and admin can update roles
        if requester_role not in [MemberRole.owner, MemberRole.admin]:
            raise ValueError("Access denied: Only owners and admins can update member roles")
        
        # Find the member to update
        member_to_update = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.id == payload.member_id)
            .filter(ProjectMember.project_id == payload.project_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        
        if not member_to_update:
            raise ValueError("Member not found or not active in this project")
        
        # Prevent self-role change (optional, but good practice)
        if str(member_to_update.user_id) == user_id:
            raise ValueError("You cannot change your own role")
        
        # Convert schema enum to model enum
        new_role = MemberRole[payload.role.value]
        
        # Permission checks based on requester role
        if requester_role == MemberRole.owner:
            # Owner cannot assign owner role to anyone
            if new_role == MemberRole.owner:
                raise ValueError("Access denied: Owner cannot assign owner role")
        
        elif requester_role == MemberRole.admin:
            # Admin cannot assign admin or owner roles
            if new_role == MemberRole.admin:
                raise ValueError("Access denied: Admins cannot assign admin role")
            if new_role == MemberRole.owner:
                raise ValueError("Access denied: Admins cannot assign owner role")
            # Admin cannot change owner's role
            if member_to_update.role == MemberRole.owner:
                raise ValueError("Access denied: Admins cannot change owner's role")
        
        # Update the role
        member_to_update.role = new_role
        self.db.commit()
        self.db.refresh(member_to_update)
        
        return ProjectMemberResponse(
            id=member_to_update.id,
            user_id=member_to_update.user_id,
            project_id=member_to_update.project_id,
            role=member_to_update.role.value,
            status=member_to_update.status.value
        )

    def remove_member(self, payload: MemberRemoveRequest, token: str) -> ProjectMemberResponse:
        """Remove a member from a project by changing their status to 'remove'.
        
        Rules:
        - Owner can remove admin/member/viewer, but cannot remove owner
        - Admin can only remove member/viewer, cannot remove owner or admin
        - Member and viewer cannot remove anyone
        """
        user_id = self._authenticate_user(token)
        
        # Verify project exists
        project = self.db.query(ProjectModel).filter(ProjectModel.id == str(payload.project_id)).first()
        if not project:
            raise ValueError("Project not found")
        
        # Get the requester's role in the project
        requester_role = self._get_user_project_role(user_id, str(payload.project_id))
        if not requester_role:
            raise ValueError("Access denied: You are not a member of this project")
        
        # Check permissions: Only owner and admin can remove members
        if requester_role not in [MemberRole.owner, MemberRole.admin]:
            raise ValueError("Access denied: Only owners and admins can remove members")
        
        # Find the member to remove
        member_to_remove = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.id == payload.member_id)
            .filter(ProjectMember.project_id == payload.project_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        
        if not member_to_remove:
            raise ValueError("Member not found or not active in this project")
        
        # Prevent self-removal
        if str(member_to_remove.user_id) == user_id:
            raise ValueError("You cannot remove yourself from the project")
        
        # Permission checks based on requester role
        if requester_role == MemberRole.owner:
            # Owner cannot remove another owner
            if member_to_remove.role == MemberRole.owner:
                raise ValueError("Access denied: Owner cannot remove another owner")
        
        elif requester_role == MemberRole.admin:
            # Admin cannot remove owner or admin
            if member_to_remove.role == MemberRole.owner:
                raise ValueError("Access denied: Admins cannot remove owner")
            if member_to_remove.role == MemberRole.admin:
                raise ValueError("Access denied: Admins cannot remove other admins")
        
        # Update member status to 'remove' and set left_at timestamp
        member_to_remove.status = MemberStatus.remove
        member_to_remove.left_at = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        self.db.commit()
        self.db.refresh(member_to_remove)
        
        return ProjectMemberResponse(
            id=member_to_remove.id,
            user_id=member_to_remove.user_id,
            project_id=member_to_remove.project_id,
            role=member_to_remove.role.value,
            status=member_to_remove.status.value
        )

    