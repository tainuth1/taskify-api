from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from app.controllers.project_controller import ProjectTypeModel
from app.core.config import settings
from app.models import ProjectMember, Task, User
from app.models.project import Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.schemas.task import TaskCreate, TaskPriority, TaskResponse, TaskStatus
from app.models.task import TaskStatus as TaskStatusModel, TaskPriority as TaskPriorityModel


class TaskController:
    def __init__(self, db: Session) -> None:
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

    def _check_project_access(self, user_id: str, project_id: str) -> bool:
        """Check if user has access to a project.
        
        For personal projects: user must be owner
        For group projects: user must be active member and role must be an owner or admin
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
    
    def _can_create_task_in_project(self, user_id: str, project_id: str) -> tuple[bool, str]:
        """Check if user can create tasks in a project.
        Returns: (allowed: bool, reason: str)
        """
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            return False, "Project not found"

        # Check access
        if not self._check_project_access(user_id, project_id):
            return False, "Access denied"
        
        # Personal project: only owner can create
        if project.type == ProjectTypeModel.personal:
            role = self._get_user_project_role(user_id, project_id)
            if role != MemberRole.owner:
                return False, "Only project owner can create tasks"
            return True, ""
        # Group project: only owners and admins can create
        else:
            role = self._get_user_project_role(user_id, project_id)
            if role not in [MemberRole.owner, MemberRole.admin]:
                return False, "Only owners and admins can create tasks"
            return True, ""

    def create_task(self, task_data: TaskCreate, token: str) -> TaskResponse:
        """Create a task. Can be personal task or project task.
        Returns the created task.
        """
        # Authenticate user
        user_id = self._authenticate_user(token)
        
        # Convert schema enums to model enums which can use to insert into database
        task_status = TaskStatusModel.pending
        if task_data.status.value == "in_progress":
            task_status = TaskStatusModel.in_progress
        elif task_data.status.value == "stuck":
            task_status = TaskStatusModel.stuck
        elif task_data.status.value == "done":
            task_status = TaskStatusModel.done

        task_priority = TaskPriorityModel.low
        if task_data.priority.value == "medium":
            task_priority = TaskPriorityModel.medium
        elif task_data.priority.value == "high":
            task_priority = TaskPriorityModel.high

        # Personal task (no project)
        if task_data.project_id is None:
            new_task = Task(
                project_id=None,
                user_id=user_id,  # Set to creator for personal tasks
                title=task_data.title,
                description=task_data.description,
                priority=task_priority,
                status=task_status,
                due_date=task_data.due_date,
                created_by=user_id
            )
        else:
            # Project task
            # Validate project and permissions
            allowed, reason = self._can_create_task_in_project(user_id, str(task_data.project_id))
            if not allowed:
                raise ValueError(reason)
            
            new_task = Task(
                project_id=task_data.project_id,
                user_id=None,  # None for project tasks
                title=task_data.title,
                description=task_data.description,
                priority=task_priority,
                status=task_status,
                due_date=task_data.due_date,
                created_by=user_id
            )

        self.db.add(new_task)
        self.db.commit()
        self.db.refresh(new_task)

        # Convert model enums back to schema enums for response
        status_enum = TaskStatus.pending
        if new_task.status == TaskStatusModel.in_progress:
            status_enum = TaskStatus.in_progress
        elif new_task.status == TaskStatusModel.stuck:
            status_enum = TaskStatus.stuck
        elif new_task.status == TaskStatusModel.done:
            status_enum = TaskStatus.done
        
        priority_enum = TaskPriority.low
        if new_task.priority == TaskPriorityModel.medium:
            priority_enum = TaskPriority.medium
        elif new_task.priority == TaskPriorityModel.high:
            priority_enum = TaskPriority.high

        task_response = TaskResponse(
            id=new_task.id,
            project_id=new_task.project_id,
            user_id=new_task.user_id,
            title=new_task.title,
            description=new_task.description,
            priority=priority_enum,
            status=status_enum,
            due_date=new_task.due_date,
            created_by=new_task.created_by,
            created_at=new_task.created_at,
            updated_at=new_task.updated_at
        )

        return task_response

