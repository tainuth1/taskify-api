from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import enum

class SubTaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    stuck = "stuck"
    done = "done"

# app/schemas/subtask.py
class SubTaskCreate(BaseModel):
    tasks_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    status: SubTaskStatus = SubTaskStatus.pending

class SubTaskUpdate(BaseModel):
    id: uuid.UUID
    title: str | None = Field(None, min_length=1, max_length=255)
    status: SubTaskStatus | None = None

    class Config:
        from_attributes = True

class SubTaskResponse(BaseModel):
    id: uuid.UUID
    tasks_id: uuid.UUID
    title: str
    status: SubTaskStatus
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

class SubTaskStatusUpdate(BaseModel):
    subtask_id: uuid.UUID
    status: SubTaskStatus

    class Config:
        from_attributes = True