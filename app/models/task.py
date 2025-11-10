from sqlalchemy import Column, String, DateTime, ForeignKey, func, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Enum as SqlEnum
import uuid
import enum
from app.database import Base

class TaskStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    stuck = "stuck"
    done = "done"

class TaskPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class Task(Base):
    __tablename__ = "tasks"
    passive_deletion = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    priority = Column(SqlEnum(TaskPriority, name="task_priority"), nullable=False, default=TaskPriority.low)
    status = Column(SqlEnum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.pending)
    due_date = Column(Date, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())