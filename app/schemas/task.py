from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional, List
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

class TaskUpdate(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[date] = None

    class Config:
        from_attributes = True

class TaskStatusUpdate(BaseModel):
    task_id: uuid.UUID
    status: TaskStatus

    class Config:
        from_attributes = True

class TaskResponse(TaskBase):
    id: uuid.UUID
    project_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]  # Only set for personal tasks
    created_by: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    assignees: List["TaskAssigneeResponse"] = []  # List of assignees

    class Config:
        from_attributes = True

# Import at the end to avoid circular imports
from app.schemas.subtask import SubTaskResponse
from app.schemas.task_assignee import TaskAssigneeResponse
TaskResponse.model_rebuild()