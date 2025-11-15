from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ProjectMember, SubTask, Task, User, Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.schemas.subtask import SubTaskCreate, SubTaskResponse, SubTaskUpdate
from app.models.subtask import TaskStatus as SubTaskStatusModel
from app.schemas.subtask import SubTaskStatus
from app.models import ProjectMember, SubTask, Task, User, Project as ProjectModel, TaskAssignee
from app.controllers.project_controller import ProjectTypeModel

class SubTaskController:
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

    def _check_project_membership(self, user_id: str, project_id: str) -> bool:
        """Check if user is an active member of the project."""
        member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id)
            .filter(ProjectMember.user_id == user_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        return member is not None

    def _can_view_subtasks(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can view subtasks for a task.
        Returns: (allowed: bool, reason: str)
        
        Rules:
        - If task belongs to a project: user must be an active project member
        - If task is personal: user must be the creator
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "Access denied"
            return True, ""
        
        # Project task - check if user is a project member
        if not self._check_project_membership(user_id, str(task.project_id)):
            return False, "Access denied. You must be a project member to view subtasks."
        
        return True, ""

    def get_subtasks_by_task(self, task_id: str, token: str) -> list[SubTaskResponse]:
        """Get all subtasks for a task.
        
        Rules:
        - If task belongs to a project: user must be an active project member
        - If task is personal: user must be the creator
        
        Returns list of subtasks.
        """
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check if user can view subtasks for this task
        allowed, reason = self._can_view_subtasks(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Get all subtasks for this task
        subtasks = (
            self.db.query(SubTask)
            .filter(SubTask.tasks_id == task_id)
            .order_by(SubTask.created_at.asc())
            .all()
        )
        
        # Convert to response format
        result = []
        for subtask in subtasks:
            # Convert model enum to schema enum
            status_enum = SubTaskStatus.pending
            if subtask.status == SubTaskStatusModel.in_progress:
                status_enum = SubTaskStatus.in_progress
            elif subtask.status == SubTaskStatusModel.stuck:
                status_enum = SubTaskStatus.stuck
            elif subtask.status == SubTaskStatusModel.done:
                status_enum = SubTaskStatus.done
            
            result.append(SubTaskResponse(
                id=subtask.id,
                tasks_id=subtask.tasks_id,
                title=subtask.title,
                status=status_enum,
                created_at=subtask.created_at,
                updated_at=subtask.updated_at
            ))
        
        return result

    def _can_create_subtask(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can create subtasks for a task.
        Returns: (allowed: bool, reason: str)
        
        Permissions:
        - Personal task: user must be the creator (user_id or created_by matches)
        - Project task: user must be owner or admin in the project
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only create subtasks for your own personal tasks"
            return True, ""
        
        # Project task - check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            return False, "Project not found"
        
        # Get user's role in the project
        role = self._get_user_project_role(user_id, str(task.project_id))
        if not role:
            return False, "Access denied"
        
        # Only owner and admin can create subtasks
        if role not in [MemberRole.owner, MemberRole.admin]:
            return False, "Only owners and admins can create subtasks"
        
        return True, ""

    def create_subtask(self, subtask_data: SubTaskCreate, token: str) -> SubTaskResponse:
        """Create a subtask for a task.
        
        Only owners and admins can create subtasks.
        Subtasks can only be created for project tasks.
        
        Args:
            subtask_data: SubTaskCreate schema with task_id and title
            token: Authentication token
            
        Returns:
            SubTaskResponse with created subtask details
            
        Raises:
            ValueError: If task not found, access denied, or insufficient permissions
        """
        # Authenticate user
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == subtask_data.tasks_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check permissions
        allowed, reason = self._can_create_subtask(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Convert schema enum to model enum
        status_model = SubTaskStatusModel.pending
        if subtask_data.status.value == "in_progress":
            status_model = SubTaskStatusModel.in_progress
        elif subtask_data.status.value == "stuck":
            status_model = SubTaskStatusModel.stuck
        elif subtask_data.status.value == "done":
            status_model = SubTaskStatusModel.done
        
        # Create subtask
        new_subtask = SubTask(
            tasks_id=subtask_data.tasks_id,
            title=subtask_data.title,
            status=status_model
        )
        
        self.db.add(new_subtask)
        self.db.commit()
        self.db.refresh(new_subtask)
        
        # Convert model enum back to schema enum
        status_enum = SubTaskStatus.pending
        if new_subtask.status == SubTaskStatusModel.in_progress:
            status_enum = SubTaskStatus.in_progress
        elif new_subtask.status == SubTaskStatusModel.stuck:
            status_enum = SubTaskStatus.stuck
        elif new_subtask.status == SubTaskStatusModel.done:
            status_enum = SubTaskStatus.done
        
        return SubTaskResponse(
            id=new_subtask.id,
            tasks_id=new_subtask.tasks_id,
            title=new_subtask.title,
            status=status_enum,
            created_at=new_subtask.created_at,
            updated_at=new_subtask.updated_at
        )

    def _can_update_subtask(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can update subtasks for a task.
        Returns: (allowed: bool, reason: str)
        
        Permissions:
        - Personal task: user must be the creator (user_id or created_by matches)
        - Project task: user must be owner or admin in the project
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only update subtasks for your own personal tasks"
            return True, ""
        
        # Project task - check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            return False, "Project not found"
        
        # Get user's role in the project
        role = self._get_user_project_role(user_id, str(task.project_id))
        if not role:
            return False, "Access denied"
        
        # Only owner and admin can update subtasks
        if role not in [MemberRole.owner, MemberRole.admin]:
            return False, "Only owners and admins can update subtasks"
        
        return True, ""

    def update_subtask(self, updated_subtask: SubTaskUpdate, token: str) -> SubTaskResponse:
        """Update a subtask. Only owners and admins can update.
        
        Validates permissions:
        - Personal task: user must be the creator (owner)
        - Project task: user must be owner or admin
        
        Args:
            updated_subtask: SubTaskUpdate schema with subtask id and fields to update
            token: Authentication token
            
        Returns:
            SubTaskResponse with updated subtask details
            
        Raises:
            ValueError: If subtask not found, access denied, or insufficient permissions
        """
        user_id = self._authenticate_user(token)
        
        # Get subtask
        subtask = self.db.query(SubTask).filter(SubTask.id == updated_subtask.id).first()
        if not subtask:
            raise ValueError("Subtask not found")
        
        # Get the parent task
        task = self.db.query(Task).filter(Task.id == subtask.tasks_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check update permissions
        allowed, reason = self._can_update_subtask(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Update only provided fields
        if updated_subtask.title is not None:
            subtask.title = updated_subtask.title
        
        if updated_subtask.status is not None:
            # Convert schema enum to model enum
            if updated_subtask.status.value == "pending":
                subtask.status = SubTaskStatusModel.pending
            elif updated_subtask.status.value == "in_progress":
                subtask.status = SubTaskStatusModel.in_progress
            elif updated_subtask.status.value == "stuck":
                subtask.status = SubTaskStatusModel.stuck
            elif updated_subtask.status.value == "done":
                subtask.status = SubTaskStatusModel.done
        
        self.db.commit()
        self.db.refresh(subtask)
        
        # Convert model enum back to schema enum
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

    def _can_delete_subtask(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can delete subtasks for a task.
        Returns: (allowed: bool, reason: str)
        
        Permissions:
        - Personal task: user must be the creator (user_id or created_by matches)
        - Project task: user must be owner or admin in the project
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only delete subtasks for your own personal tasks"
            return True, ""
        
        # Project task - check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            return False, "Project not found"
        
        # Get user's role in the project
        role = self._get_user_project_role(user_id, str(task.project_id))
        if not role:
            return False, "Access denied"
        
        # Only owner and admin can delete subtasks
        if role not in [MemberRole.owner, MemberRole.admin]:
            return False, "Only owners and admins can delete subtasks"
        
        return True, ""

    def delete_subtask(self, token: str, subtask_id: str) -> dict:
        """Delete a subtask. Hard delete (permanent).
        
        Validates permissions:
        - Personal task: user must be the creator
        - Project task: user must be owner or admin
        
        Args:
            token: Authentication token
            subtask_id: Subtask ID to delete
            
        Returns:
            Success message with subtask details before deletion
            
        Raises:
            ValueError: If subtask not found, access denied, or insufficient permissions
        """
        user_id = self._authenticate_user(token)
        
        # Get subtask
        subtask = self.db.query(SubTask).filter(SubTask.id == subtask_id).first()
        if not subtask:
            raise ValueError("Subtask not found")
        
        # Get the parent task
        task = self.db.query(Task).filter(Task.id == subtask.tasks_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check delete permissions
        allowed, reason = self._can_delete_subtask(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Store subtask info for response before deletion
        subtask_info = {
            "id": str(subtask.id),
            "tasks_id": str(subtask.tasks_id),
            "title": subtask.title
        }
        
        # Hard delete the subtask
        self.db.delete(subtask)
        self.db.commit()
        
        return {
            "message": "Subtask deleted successfully",
            "deleted_subtask": subtask_info
        }

    def _can_update_subtask_status(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can update subtask status.
        
        Returns: (allowed: bool, reason: str)
        
        Permissions:
        - Personal task: only creator can update
        - Personal project: only owner can update any subtask
        - Group project: 
            - Owner/Admin: can update any subtask status
            - Member: can only update if assigned to the task
            - Viewer: cannot update
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only update status of subtasks for your own personal tasks"
            return True, ""

        # Project task - check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            return False, "Project not found"

        # Get user's role in the project
        role = self._get_user_project_role(user_id, str(task.project_id))
        if not role:
            return False, "Access denied"
        
        # Personal project: only owner can update
        if project.type == ProjectTypeModel.personal:
            if role != MemberRole.owner:
                return False, "Only project owner can update subtask status"
            return True, ""
        
        # Group project: check role permissions
        else:
            # Owner and admin can update any subtask
            if role in [MemberRole.owner, MemberRole.admin]:
                return True, ""
            
            # Viewer cannot update
            if role == MemberRole.viewer:
                return False, "Viewers cannot update subtask status"
            
            # Member: can only update if assigned to the task
            if role == MemberRole.member:
                # Check if user is assigned to this task
                assignment = (
                    self.db.query(TaskAssignee)
                    .filter(TaskAssignee.tasks_id == task.id)
                    .filter(TaskAssignee.user_id == user_id)
                    .first()
                )
                
                if not assignment:
                    return False, "Members can only update status of subtasks for tasks assigned to them"
                return True, ""
            
            return False, "Access denied"

    def update_subtask_status(self, subtask_id: str, new_status: SubTaskStatus, token: str) -> SubTaskResponse:
        """Update subtask status only.
        
        Permissions:
        - Personal task: only creator can update
        - Personal project: only owner can update any subtask
        - Group project:
            - Owner/Admin: can update any subtask status
            - Member: can only update status of subtasks for assigned tasks
            - Viewer: cannot update
        
        Args:
            subtask_id: Subtask ID to update
            new_status: New status value
            token: Authentication token
        
        Returns:
            Updated SubTaskResponse
        
        Raises:
            ValueError: If subtask not found, access denied, or insufficient permissions
        """
        user_id = self._authenticate_user(token)
        
        # Get subtask
        subtask = self.db.query(SubTask).filter(SubTask.id == subtask_id).first()
        if not subtask:
            raise ValueError("Subtask not found")
        
        # Get the parent task
        task = self.db.query(Task).filter(Task.id == subtask.tasks_id).first()
        if not task:
            raise ValueError("Task not found")

        # Check status update permissions
        allowed, reason = self._can_update_subtask_status(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Convert schema enum to model enum
        status_model = SubTaskStatusModel.pending
        if new_status.value == "in_progress":
            status_model = SubTaskStatusModel.in_progress
        elif new_status.value == "stuck":
            status_model = SubTaskStatusModel.stuck
        elif new_status.value == "done":
            status_model = SubTaskStatusModel.done

        # Update status
        subtask.status = status_model
        
        self.db.commit()
        self.db.refresh(subtask)
        
        # Convert model enum back to schema enum
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