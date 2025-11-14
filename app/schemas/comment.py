from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid
from app.schemas.user import User


class CommentCreate(BaseModel):
    tasks_id: uuid.UUID
    content: str = Field(..., min_length=1)


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tasks_id: uuid.UUID
    content: Optional[str] = None
    created_at: datetime
    user: Optional[User] = None

    class Config:
        from_attributes = True

