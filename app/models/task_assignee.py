from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tasks_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())