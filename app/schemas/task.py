from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import enum

from app.schemas.comment import CommentResponse
from app.schemas.subtask import SubTaskResponse

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

class SubTaskCount(BaseModel):
    total: int
    done: int

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

class CreatedByUser(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    profile: Optional[str] = None

class TaskResponse(BaseModel):
    title: str
    description: Optional[str]
    priority: str
    status: str
    due_date: Optional[str] = None
    id: str
    project_id: Optional[str] = None
    user_id: str
    created_by: str
    created_by_user: CreatedByUser
    created_at: str
    updated_at: Optional[str] = None
    subtask: SubTaskCount
    assignees: List[CreatedByUser] = []

    class Config:
        from_attributes = True

class TaskDetailResponse(TaskResponse):
    subtasks: List[SubTaskResponse]
    comments: List[CommentResponse]
