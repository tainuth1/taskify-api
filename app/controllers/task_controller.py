from operator import or_
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.controllers.project_controller import ProjectTypeModel
from app.core.config import settings
from app.models import ProjectMember, SubTask, Task, User
from app.models.project import Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.schemas.subtask import SubTaskResponse, SubTaskStatus
from app.schemas.task import TaskCreate, TaskPriority, TaskResponse, TaskStatus
from app.models.task import TaskStatus as TaskStatusModel, TaskPriority as TaskPriorityModel
from app.models.subtask import TaskStatus as SubTaskStatusModel


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

    def _check_project_view_access(self, user_id: str, project_id: str) -> bool:
        """Check if user can view tasks in a project.
        
        For personal projects: user must be owner
        For group projects: user must be active member (any role)
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
        # Group projects: must be active member (any role)
        else:
            return member is not None
    
    def _model_to_schema_subtask(self, subtask: SubTask) -> SubTaskResponse:
        """Convert SubTask model to SubTaskResponse schema."""
        # Convert model enum to schema enum
        status_enum = SubTaskStatus.pending
        if subtask.status == SubTaskStatusModel.in_progress:
            status_enum = SubTaskStatus.in_progress
        elif subtask.status == SubTaskStatusModel.stuck:
            status_enum = SubTaskStatus.stuck
        elif subtask.status == SubTaskStatusModel.done:
            status_enum = SubTaskStatus.done
        
        return SubTaskResponse(
            id=subtask.id,
            tasks_id=subtask.tasks_id,
            title=subtask.title,
            status=status_enum,
            created_at=subtask.created_at,
            updated_at=subtask.updated_at
        )

    def _model_to_schema_task(self, task: Task, include_subtasks: bool = False) -> TaskResponse:
        """Convert Task model to TaskResponse schema.
        
        Args:
            task: Task model instance
            include_subtasks: If True, includes subtasks in the response
        """
        # Convert model enums back to schema enums
        status_enum = TaskStatus.pending
        if task.status == TaskStatusModel.in_progress:
            status_enum = TaskStatus.in_progress
        elif task.status == TaskStatusModel.stuck:
            status_enum = TaskStatus.stuck
        elif task.status == TaskStatusModel.done:
            status_enum = TaskStatus.done
        
        priority_enum = TaskPriority.low
        if task.priority == TaskPriorityModel.medium:
            priority_enum = TaskPriority.medium
        elif task.priority == TaskPriorityModel.high:
            priority_enum = TaskPriority.high
        
        # Fetch subtasks if requested
        subtasks = []
        if include_subtasks:
            subtask_models = (
                self.db.query(SubTask)
                .filter(SubTask.tasks_id == task.id)
                .all()
            )
            subtasks = [self._model_to_schema_subtask(st) for st in subtask_models]
        
        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            priority=priority_enum,
            status=status_enum,
            due_date=task.due_date,
            created_by=task.created_by,
            created_at=task.created_at,
            updated_at=task.updated_at,
            subtasks=subtasks
        )

    def get_all_tasks(self, token: str) -> list[TaskResponse]:
        """Get all personal tasks (not belonging to any project) for the authenticated user.
        
        Only returns personal tasks (project_id=None, user_id=user_id).
        Tasks inside any project are excluded from this view.
        """
        user_id = self._authenticate_user(token)

        # Only fetch personal tasks (not belonging to any project)
        tasks = (
            self.db.query(Task)
            .filter(
                Task.project_id.is_(None),
                Task.user_id == user_id
            )
            .all()
        )
        
        # Convert to response format
        return [self._model_to_schema_task(task) for task in tasks]

    def get_tasks_by_project(self, token: str, project_id: str) -> list[TaskResponse]:
        """Get all tasks for a specific project.
        
        Validates user has access to the project before returning tasks.
        """
        user_id = self._authenticate_user(token)
        
        # Check if project exists
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check view access
        if not self._check_project_view_access(user_id, project_id):
            raise ValueError("Access denied")
        
        # Get all tasks for this project
        tasks = (
            self.db.query(Task)
            .filter(Task.project_id == project_id)
            .all()
        )
        
        return [self._model_to_schema_task(task, include_subtasks=True) for task in tasks]

    def get_task_by_id(self, token: str, task_id: str) -> TaskResponse:
        """Get a single task by ID.
        
        Validates user has access to the task:
        - Personal task: user must be the creator (user_id or created_by)
        - Project task: user must have access to the project
        """
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check access
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                raise ValueError("Access denied")
        else:
            # Project task - check project access
            if not self._check_project_view_access(user_id, str(task.project_id)):
                raise ValueError("Access denied")
        
        return self._model_to_schema_task(task, include_subtasks=True)

    def _can_delete_task(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can delete a task.
        Returns: (allowed: bool, reason: str)
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only delete your own personal tasks"
            return True, ""
        
        # Project task - check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            return False, "Project not found"
        
        # Get user's role in the project
        role = self._get_user_project_role(user_id, str(task.project_id))
        if not role:
            return False, "Access denied"
        
        # Personal project: only owner can delete
        if project.type == ProjectTypeModel.personal:
            if role != MemberRole.owner:
                return False, "Only project owner can delete tasks"
            return True, ""
        
        # Group project: only owner and admin can delete
        else:
            if role not in [MemberRole.owner, MemberRole.admin]:
                return False, "Only owners and admins can delete tasks"
            return True, ""

    def delete_task(self, token: str, task_id: str) -> dict:
        """Delete a task. Hard delete (permanent).
        
        Validates permissions:
        - Personal task: user must be the creator
        - Personal project task: user must be owner
        - Group project task: user must be owner or admin
        
        Raises ValueError if task not found, access denied, or insufficient permissions.
        Returns a success message with task details before deletion.
        """
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check delete permissions
        allowed, reason = self._can_delete_task(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Store task info for response before deletion
        task_info = {
            "id": str(task.id),
            "title": task.title,
            "project_id": str(task.project_id) if task.project_id else None,
            "user_id": str(task.user_id) if task.user_id else None
        }
        
        # Hard delete the task (CASCADE will handle subtasks automatically)
        self.db.delete(task)
        self.db.commit()
        
        return {
            "message": "Task deleted successfully",
            "deleted_task": task_info
        }