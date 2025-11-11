from operator import or_
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.controllers.project_controller import ProjectTypeModel
from app.core.config import settings
from app.models import ProjectMember, SubTask, Task, User, TaskAssignee
from app.models.project import Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.schemas.subtask import SubTaskResponse, SubTaskStatus
from app.schemas.task import TaskCreate, TaskPriority, TaskResponse, TaskStatus, TaskUpdate
from app.schemas.task_assignee import TaskAssigneeResponse
from app.schemas.user import User as UserSchema
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
    
    def _model_to_schema_assignee(self, assignee: TaskAssignee) -> TaskAssigneeResponse:
        """Convert TaskAssignee model to TaskAssigneeResponse schema."""
        # Fetch user details
        user = self.db.query(User).filter(User.id == assignee.user_id).first()
        if not user:
            raise ValueError(f"User {assignee.user_id} not found")
        
        user_schema = UserSchema.model_validate(user)
        
        return TaskAssigneeResponse(
            id=assignee.id,
            user_id=assignee.user_id,
            tasks_id=assignee.tasks_id,
            assigned_by=assignee.assigned_by,
            assigned_at=assignee.assigned_at,
            user=user_schema
        )

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

    def _model_to_schema_task(self, task: Task, include_subtasks: bool = False, include_assignees: bool = False) -> TaskResponse:
        """Convert Task model to TaskResponse schema.
        
        Args:
            task: Task model instance
            include_subtasks: If True, includes subtasks in the response
            include_assignees: If True, includes assignees in the response
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
        
        # Fetch assignees if requested
        assignees = []
        if include_assignees:
            assignee_models = (
                self.db.query(TaskAssignee)
                .filter(TaskAssignee.tasks_id == task.id)
                .all()
            )
            assignees = [self._model_to_schema_assignee(assignee) for assignee in assignee_models]
        
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
            subtasks=subtasks,
            assignees=assignees
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
        Includes subtasks and assignees for each task.
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
        
        # Convert to response format with subtasks and assignees
        return [self._model_to_schema_task(task, include_subtasks=True, include_assignees=True) for task in tasks]

    def get_task_by_id(self, token: str, task_id: str) -> TaskResponse:
        """Get a single task by ID.
        
        Validates user has access to the task:
        - Personal task: user must be the creator (user_id or created_by)
        - Project task: user must have access to the project
        Includes subtasks and assignees for the task.
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
        
        # Return task with subtasks and assignees
        return self._model_to_schema_task(task, include_subtasks=True, include_assignees=True)

    def _can_update_task(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can update a task.
        Returns: (allowed: bool, reason: str)
        """
        # Personal task (no project)
        if task.project_id is None:
            # User must be the creator (owner)
            if str(task.user_id) != user_id and str(task.created_by) != user_id:
                return False, "You can only update your own personal tasks"
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
                return False, "Only project owner can update tasks"
            return True, ""
        
        # Group project: only owner and admin can update
        else:
            if role not in [MemberRole.owner, MemberRole.admin]:
                return False, "Only owners and admins can update tasks"
            return True, ""

    def update_task(self, updated_task: TaskUpdate, token: str) -> TaskResponse:
        """Update a task. Only owners and admins can update.
        
        Validates permissions:
        - Personal task: user must be the creator (owner)
        - Personal project task: user must be owner
        - Group project task: user must be owner or admin
        
        Raises ValueError if task not found, access denied, or insufficient permissions.
        Returns the updated task.
        """
        user_id = self._authenticate_user(token)

        # Get task
        task = self.db.query(Task).filter(Task.id == updated_task.id).first()
        if not task:
            raise ValueError("Task not found")

        # Check update permissions
        allowed, reason = self._can_update_task(user_id, task)
        if not allowed:
            raise ValueError(reason)

        # Update only provided fields
        if updated_task.title is not None:
            task.title = updated_task.title
        
        if updated_task.description is not None:
            task.description = updated_task.description

        if updated_task.priority is not None:
            # Convert schema enum to model enum
            if updated_task.priority.value == "low":
                task.priority = TaskPriorityModel.low
            elif updated_task.priority.value == "medium":
                task.priority = TaskPriorityModel.medium
            elif updated_task.priority.value == "high":
                task.priority = TaskPriorityModel.high
        
        if updated_task.status is not None:
            # Convert schema enum to model enum
            if updated_task.status.value == "pending":
                task.status = TaskStatusModel.pending
            elif updated_task.status.value == "in_progress":
                task.status = TaskStatusModel.in_progress
            elif updated_task.status.value == "stuck":
                task.status = TaskStatusModel.stuck
            elif updated_task.status.value == "done":
                task.status = TaskStatusModel.done

        if updated_task.due_date is not None:
            task.due_date = updated_task.due_date

        self.db.commit()
        self.db.refresh(task)

        # Return updated task with subtasks
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

    def assign_task_to_user(self, token: str, task_id: str, user_id: str) -> TaskAssigneeResponse:
        """Assign a task to a user.
        
        Only owners and admins can assign tasks.
        - Personal project: only owner can assign
        - Group project: only owner or admin can assign
        
        Args:
            token: Authentication token
            task_id: Task ID to assign
            user_id: User ID to assign the task to
        
        Returns:
            TaskAssigneeResponse with assignment details
        """
        authenticated_user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check if task belongs to a project (assignments only for project tasks)
        if task.project_id is None:
            raise ValueError("Cannot assign personal tasks. Assignments are only for project tasks.")
        
        # Check if user to be assigned exists
        assignee_user = self.db.query(User).filter(User.id == user_id).first()
        if not assignee_user:
            raise ValueError("User to assign not found")
        
        if not assignee_user.is_active:
            raise ValueError("Cannot assign task to inactive user")
        
        # Check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Get authenticated user's role
        role = self._get_user_project_role(authenticated_user_id, str(task.project_id))
        if not role:
            raise ValueError("Access denied")
        
        # Check permissions: only owner/admin can assign
        if project.type == ProjectTypeModel.personal:
            if role != MemberRole.owner:
                raise ValueError("Only project owner can assign tasks")
        else:  # group project
            if role not in [MemberRole.owner, MemberRole.admin]:
                raise ValueError("Only owners and admins can assign tasks")
        
        # Check if assignee is a member of the project
        assignee_member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == task.project_id)
            .filter(ProjectMember.user_id == user_id)
            .filter(ProjectMember.status == MemberStatus.active)
            .first()
        )
        
        if not assignee_member:
            raise ValueError("Cannot assign task to user who is not a project member")
        
        # Check if task is already assigned to this user
        existing_assignment = (
            self.db.query(TaskAssignee)
            .filter(TaskAssignee.tasks_id == task_id)
            .filter(TaskAssignee.user_id == user_id)
            .first()
        )
        
        if existing_assignment:
            raise ValueError("Task is already assigned to this user")
        
        # Create assignment
        new_assignment = TaskAssignee(
            user_id=user_id,
            tasks_id=task_id,
            assigned_by=authenticated_user_id
        )
        
        self.db.add(new_assignment)
        self.db.commit()
        self.db.refresh(new_assignment)
        
        return self._model_to_schema_assignee(new_assignment)

    def unassign_task_from_user(self, token: str, task_id: str, user_id: str) -> dict:
        """Unassign a task from a user.
        
        Only owners and admins can unassign tasks.
        - Personal project: only owner can unassign
        - Group project: only owner or admin can unassign
        
        Args:
            token: Authentication token
            task_id: Task ID to unassign
            user_id: User ID to unassign the task from
        
        Returns:
            Success message with assignment details
        """
        authenticated_user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check if task belongs to a project
        if task.project_id is None:
            raise ValueError("Cannot unassign personal tasks. Unassignments are only for project tasks.")
        
        # Check project and permissions
        project = self.db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Get authenticated user's role
        role = self._get_user_project_role(authenticated_user_id, str(task.project_id))
        if not role:
            raise ValueError("Access denied")
        
        # Check permissions: only owner/admin can unassign
        if project.type == ProjectTypeModel.personal:
            if role != MemberRole.owner:
                raise ValueError("Only project owner can unassign tasks")
        else:  # group project
            if role not in [MemberRole.owner, MemberRole.admin]:
                raise ValueError("Only owners and admins can unassign tasks")
        
        # Find assignment
        assignment = (
            self.db.query(TaskAssignee)
            .filter(TaskAssignee.tasks_id == task_id)
            .filter(TaskAssignee.user_id == user_id)
            .first()
        )
        
        if not assignment:
            raise ValueError("Task is not assigned to this user")
        
        # Store info before deletion
        assignment_info = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "assigned_by": str(assignment.assigned_by)
        }
        
        # Delete assignment
        self.db.delete(assignment)
        self.db.commit()
        
        return {
            "message": "Task unassigned successfully",
            "unassigned": assignment_info
        }