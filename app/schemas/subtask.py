from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import enum

class SubTaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    stuck = "stuck"
    done = "done"

class SubTaskResponse(BaseModel):
    id: uuid.UUID
    tasks_id: uuid.UUID
    title: str
    status: SubTaskStatus
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True