from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, case
from datetime import date, datetime
from typing import List

from app.core.config import settings
from app.models import ProjectMember, SubTask, Task, User, TaskAssignee, ProjectInvite
from app.models.project import Project as ProjectModel
from app.models.project_member import MemberRole, MemberStatus
from app.models.project_invite import InviteStatus
from app.models.task import TaskStatus as TaskStatusModel, TaskPriority as TaskPriorityModel
from app.models.subtask import TaskStatus as SubTaskStatusModel
from app.controllers.project_controller import ProjectTypeModel
from app.schemas.dashboard import DashboardResponse, StatItem, HighPriorityTasks, TaskPerformance, SidebarDataResponse, GeneralData, ProjectsData, SettingsData
from app.schemas.task import TaskResponse, SubTaskCount, CreatedByUser


class ComplexUIController:
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

    def _get_user_accessible_projects(self, user_id: str) -> List[str]:
        """Get all project IDs that the user has access to (personal + group)."""
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
        return [str(p.id) for p in projects]

    def _model_to_schema_task(self, task: Task) -> TaskResponse:
        """Convert Task model to TaskResponse schema."""
        # Convert model enums to strings
        status_str = "pending"
        if task.status == TaskStatusModel.in_progress:
            status_str = "in_progress"
        elif task.status == TaskStatusModel.stuck:
            status_str = "stuck"
        elif task.status == TaskStatusModel.done:
            status_str = "done"
        
        priority_str = "low"
        if task.priority == TaskPriorityModel.medium:
            priority_str = "medium"
        elif task.priority == TaskPriorityModel.high:
            priority_str = "high"
        
        # Count subtasks
        subtasks = (
            self.db.query(SubTask)
            .filter(SubTask.tasks_id == task.id)
            .all()
        )
        total_subtasks = len(subtasks)
        done_subtasks = sum(1 for st in subtasks if st.status == SubTaskStatusModel.done)
        
        # Fetch assignees with full user data
        assignee_models = (
            self.db.query(TaskAssignee)
            .filter(TaskAssignee.tasks_id == task.id)
            .all()
        )
        assignees = []
        for assignee_model in assignee_models:
            assignee_user = self.db.query(User).filter(User.id == assignee_model.user_id).first()
            if assignee_user:
                assignees.append(CreatedByUser(
                    id=str(assignee_user.id),
                    email=assignee_user.email,
                    username=assignee_user.username,
                    full_name=assignee_user.full_name,
                    profile=assignee_user.profile
                ))
        
        # Fetch creator user information
        creator_user = self.db.query(User).filter(User.id == task.created_by).first()
        if not creator_user:
            raise ValueError(f"Creator user {task.created_by} not found")
        
        created_by_user = CreatedByUser(
            id=str(creator_user.id),
            email=creator_user.email,
            username=creator_user.username,
            full_name=creator_user.full_name,
            profile=creator_user.profile
        )
        
        # Convert dates to strings
        due_date_str = task.due_date.isoformat() if task.due_date else None
        created_at_str = task.created_at.isoformat() if task.created_at else ""
        updated_at_str = task.updated_at.isoformat() if task.updated_at else None
        
        return TaskResponse(
            id=str(task.id),
            project_id=str(task.project_id) if task.project_id else None,
            user_id=str(task.user_id) if task.user_id else "",
            title=task.title,
            description=task.description,
            priority=priority_str,
            status=status_str,
            due_date=due_date_str,
            created_by=str(task.created_by),
            created_by_user=created_by_user,
            created_at=created_at_str,
            updated_at=updated_at_str,
            subtask=SubTaskCount(total=total_subtasks, done=done_subtasks),
            assignees=assignees
        )

    def get_dashboard_data(self, token: str) -> DashboardResponse:
        """Get dashboard data for the authenticated user."""
        user_id = self._authenticate_user(token)
        
        # Get all accessible project IDs
        accessible_project_ids = self._get_user_accessible_projects(user_id)
        
        # Stats: Total projects
        total_projects = len(accessible_project_ids)
        
        # Stats: Total tasks (personal + project tasks)
        # Personal tasks: project_id is None and user_id = user_id
        # Project tasks: project_id in accessible_project_ids
        # Combine queries
        if accessible_project_ids:
            all_tasks_query = self.db.query(Task).filter(
                or_(
                    and_(Task.project_id.is_(None), Task.user_id == user_id),
                    Task.project_id.in_(accessible_project_ids)
                )
            )
        else:
            all_tasks_query = self.db.query(Task).filter(
                Task.project_id.is_(None),
                Task.user_id == user_id
            )
        
        total_tasks = all_tasks_query.count()
        
        # Stats: Total completed tasks
        completed_tasks = all_tasks_query.filter(Task.status == TaskStatusModel.done).count()
        
        # High priority tasks logic
        # Priority order: high > medium > low (for filtering)
        priority_order = case(
            (Task.priority == TaskPriorityModel.high, 1),
            (Task.priority == TaskPriorityModel.medium, 2),
            (Task.priority == TaskPriorityModel.low, 3),
            else_=4
        )
        
        # Personal high priority tasks (not done, limit 3)
        # Get high priority first, if none then order by priority level
        # Then order final result by due_date (earliest first, NULLs last)
        personal_high_priority_query = (
            self.db.query(Task)
            .filter(
                Task.project_id.is_(None),
                Task.user_id == user_id,
                Task.status != TaskStatusModel.done
            )
        )
        
        # Try to get high priority tasks first
        high_priority_personal = personal_high_priority_query.filter(
            Task.priority == TaskPriorityModel.high
        ).limit(3).all()
        
        if len(high_priority_personal) < 3:
            # If we don't have 3 high priority tasks, get more ordered by priority level
            remaining_needed = 3 - len(high_priority_personal)
            high_priority_ids = [t.id for t in high_priority_personal]
            additional_tasks = (
                personal_high_priority_query.filter(~Task.id.in_(high_priority_ids) if high_priority_ids else True)
                .order_by(priority_order)
                .limit(remaining_needed)
                .all()
            )
            personal_high_priority = high_priority_personal + additional_tasks
        else:
            personal_high_priority = high_priority_personal
        
        # Sort final result by due_date (earliest first, NULLs last)
        personal_high_priority.sort(key=lambda t: (t.due_date is None, t.due_date or date.max))
        
        # Project high priority tasks (not done, limit 3)
        # Show only tasks created by the user OR assigned to the user
        if accessible_project_ids:
            project_high_priority_query = (
                self.db.query(Task)
                .outerjoin(TaskAssignee, TaskAssignee.tasks_id == Task.id)
                .filter(
                    Task.project_id.in_(accessible_project_ids),
                    Task.status != TaskStatusModel.done,
                    or_(
                        Task.created_by == user_id,
                        TaskAssignee.user_id == user_id
                    )
                )
                .group_by(Task.id)  # Group by Task.id to avoid duplicates
            )
            
            # Try to get high priority tasks first
            high_priority_project = project_high_priority_query.filter(
                Task.priority == TaskPriorityModel.high
            ).limit(3).all()
            
            if len(high_priority_project) < 3:
                # If we don't have 3 high priority tasks, get more ordered by priority level
                remaining_needed = 3 - len(high_priority_project)
                high_priority_ids = [t.id for t in high_priority_project]
                additional_tasks = (
                    project_high_priority_query.filter(~Task.id.in_(high_priority_ids) if high_priority_ids else True)
                    .order_by(priority_order)
                    .limit(remaining_needed)
                    .all()
                )
                project_high_priority = high_priority_project + additional_tasks
            else:
                project_high_priority = high_priority_project
            
            # Sort final result by due_date (earliest first, NULLs last)
            project_high_priority.sort(key=lambda t: (t.due_date is None, t.due_date or date.max))
        else:
            project_high_priority = []
        
        # Due soon tasks (limit 5, ordered by due_date ascending)
        # Only show tasks due today or in the future, not past due dates
        today = date.today()
        if accessible_project_ids:
            due_soon_query = self.db.query(Task).filter(
                or_(
                    and_(Task.project_id.is_(None), Task.user_id == user_id),
                    Task.project_id.in_(accessible_project_ids)
                ),
                Task.due_date.isnot(None),
                Task.due_date >= today
            ).order_by(Task.due_date.asc()).limit(5)
        else:
            due_soon_query = self.db.query(Task).filter(
                Task.project_id.is_(None),
                Task.user_id == user_id,
                Task.due_date.isnot(None),
                Task.due_date >= today
            ).order_by(Task.due_date.asc()).limit(5)
        
        due_soon_tasks = due_soon_query.all()
        
        # Task performance stats
        task_performance_completed = all_tasks_query.filter(Task.status == TaskStatusModel.done).count()
        task_performance_stuck = all_tasks_query.filter(Task.status == TaskStatusModel.stuck).count()
        task_performance_in_progress = all_tasks_query.filter(Task.status == TaskStatusModel.in_progress).count()
        task_performance_pending = all_tasks_query.filter(Task.status == TaskStatusModel.pending).count()
        
        # Convert tasks to TaskResponse
        personal_high_priority_responses = [self._model_to_schema_task(task) for task in personal_high_priority]
        project_high_priority_responses = [self._model_to_schema_task(task) for task in project_high_priority]
        due_soon_responses = [self._model_to_schema_task(task) for task in due_soon_tasks]
        
        # Build response
        return DashboardResponse(
            stats=[
                StatItem(title="Total Project", value=total_projects),
                StatItem(title="Total Tasks", value=total_tasks),
                StatItem(title="Total Completed Tasks", value=completed_tasks),
            ],
            highPriorityTasks=HighPriorityTasks(
                personal=personal_high_priority_responses,
                project=project_high_priority_responses
            ),
            dueSoon=due_soon_responses,
            taskPerformance=TaskPerformance(
                totalTasks=total_tasks,
                done=task_performance_completed,
                stuck=task_performance_stuck,
                pending=task_performance_pending,
                inProgress=task_performance_in_progress
            )
        )

    def get_sidebar_data(self, token: str) -> SidebarDataResponse:
        """Get sidebar data counts for the authenticated user."""
        user_id = self._authenticate_user(token)
        
        # Get user email for checking invitations
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # General tasks: count personal tasks (project_id is null)
        # Not group project tasks, not personal project tasks - just standalone personal tasks
        personal_tasks_count = (
            self.db.query(Task)
            .filter(
                Task.project_id.is_(None),
                Task.user_id == user_id
            )
            .count()
        )
        
        # General invitations: count pending invites for user's email
        pending_invitations_count = (
            self.db.query(ProjectInvite)
            .filter(
                ProjectInvite.email == user.email,
                ProjectInvite.status == InviteStatus.pending
            )
            .count()
        )
        
        # Projects: count total accessible projects (both personal and group)
        accessible_project_ids = self._get_user_accessible_projects(user_id)
        projects_count = len(accessible_project_ids)
        
        # Settings notification: return 0 for now
        notification_count = 0
        
        return SidebarDataResponse(
            general=GeneralData(
                tasks=personal_tasks_count,
                invitations=pending_invitations_count
            ),
            projects=ProjectsData(
                projects=projects_count
            ),
            settings=SettingsData(
                notification=notification_count
            )
        )

    def get_sidebar_data_count(self, token: str):
        """Alias for get_sidebar_data for backward compatibility."""
        return self.get_sidebar_data(token)
