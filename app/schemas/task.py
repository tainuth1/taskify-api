from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import enum

class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    stuck = "stuck"
    done = "done"

class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.low
    status: TaskStatus = TaskStatus.pending
    due_date: Optional[date] = None

class TaskCreate(TaskBase):
    project_id: Optional[uuid.UUID] = None  # None for personal task

class TaskResponse(TaskBase):
    id: uuid.UUID
    project_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]  # Only set for personal tasks
    created_by: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True