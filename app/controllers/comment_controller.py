from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Comment, Task, User, ProjectMember, Project as ProjectModel
from app.models.project_member import MemberStatus
from app.models.project import ProjectType as ProjectTypeModel
from app.schemas.comment import CommentCreate, CommentUpdate, CommentResponse
from app.schemas.user import User as UserSchema


class CommentController:
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

    def _can_comment_on_task(self, user_id: str, task: Task) -> tuple[bool, str]:
        """Check if user can comment on a task.
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
            return False, "Access denied. You must be a project member to comment."
        
        return True, ""

    def create_comment(self, comment_data: CommentCreate, token: str) -> CommentResponse:
        """Create a comment on a task.
        
        Rules:
        - If task belongs to a project: user must be an active project member
        - If task is personal: user must be the creator
        
        Returns the created comment.
        """
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == comment_data.tasks_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check if user can comment on this task
        allowed, reason = self._can_comment_on_task(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Create comment
        new_comment = Comment(
            user_id=user_id,
            tasks_id=comment_data.tasks_id,
            content=comment_data.content
        )
        
        self.db.add(new_comment)
        self.db.commit()
        self.db.refresh(new_comment)
        
        # Fetch user details
        user = self.db.query(User).filter(User.id == user_id).first()
        user_schema = UserSchema.model_validate(user) if user else None
        
        return CommentResponse(
            id=new_comment.id,
            user_id=new_comment.user_id,
            tasks_id=new_comment.tasks_id,
            content=new_comment.content,
            created_at=new_comment.created_at,
            user=user_schema
        )

    def get_comments_by_task(self, task_id: str, token: str) -> list[CommentResponse]:
        """Get all comments for a task.
        
        Rules:
        - If task belongs to a project: user must be an active project member
        - If task is personal: user must be the creator
        
        Returns list of comments.
        """
        user_id = self._authenticate_user(token)
        
        # Get task
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
        
        # Check if user can view comments on this task
        allowed, reason = self._can_comment_on_task(user_id, task)
        if not allowed:
            raise ValueError(reason)
        
        # Get all comments for this task
        comments = (
            self.db.query(Comment)
            .filter(Comment.tasks_id == task_id)
            .order_by(Comment.created_at.asc())
            .all()
        )
        
        # Convert to response format
        result = []
        for comment in comments:
            user = self.db.query(User).filter(User.id == comment.user_id).first()
            user_schema = UserSchema.model_validate(user) if user else None
            
            result.append(CommentResponse(
                id=comment.id,
                user_id=comment.user_id,
                tasks_id=comment.tasks_id,
                content=comment.content,
                created_at=comment.created_at,
                user=user_schema
            ))
        
        return result

    def update_comment(self, comment_id: str, comment_data: CommentUpdate, token: str) -> CommentResponse:
        """Update a comment.
        
        Rules:
        - Only the comment owner can update their own comment
        
        Returns the updated comment.
        """
        user_id = self._authenticate_user(token)
        
        # Get comment
        comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise ValueError("Comment not found")
        
        # Check if user is the comment owner
        if str(comment.user_id) != user_id:
            raise ValueError("You can only update your own comments")
        
        # Update content
        comment.content = comment_data.content
        
        self.db.commit()
        self.db.refresh(comment)
        
        # Fetch user details
        user = self.db.query(User).filter(User.id == comment.user_id).first()
        user_schema = UserSchema.model_validate(user) if user else None
        
        return CommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            tasks_id=comment.tasks_id,
            content=comment.content,
            created_at=comment.created_at,
            user=user_schema
        )

    def delete_comment(self, comment_id: str, token: str) -> dict:
        """Delete a comment.
        
        Rules:
        - Only the comment owner can delete their own comment
        
        Returns success message with comment details before deletion.
        """
        user_id = self._authenticate_user(token)
        
        # Get comment
        comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise ValueError("Comment not found")
        
        # Check if user is the comment owner
        if str(comment.user_id) != user_id:
            raise ValueError("You can only delete your own comments")
        
        # Store comment info for response before deletion
        comment_info = {
            "id": str(comment.id),
            "tasks_id": str(comment.tasks_id),
            "content": comment.content
        }
        
        # Delete comment
        self.db.delete(comment)
        self.db.commit()
        
        return {
            "message": "Comment deleted successfully",
            "deleted_comment": comment_info
        }
