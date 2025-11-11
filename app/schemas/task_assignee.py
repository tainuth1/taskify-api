from datetime import datetime
from pydantic import BaseModel
import uuid
from app.schemas.user import User

class TaskAssigneeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tasks_id: uuid.UUID
    assigned_by: uuid.UUID
    assigned_at: datetime
    user: User  # User details for the assignee

    class Config:
        from_attributes = True

class TaskAssignRequest(BaseModel):
    user_id: uuid.UUID