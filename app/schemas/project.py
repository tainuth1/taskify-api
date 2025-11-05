from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import enum
import uuid

from app.schemas.user import User


class ProjectType(str, enum.Enum):
    personal = "personal"
    group = "group"


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: ProjectType = ProjectType.personal

    class Config:
        from_attributes = True


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[ProjectType] = None


class Project(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    members: List[dict] = []  # each item: {"user": User, "role": str}
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProjectDetailResponse(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    members: List[dict] = []  # each item: {"user": User, "role": str}
    user_role: Optional[str] = None  # Current user's role in the project
    tasks: List[dict] = []  # Structure for future task integration
    subtasks: List[dict] = []  # Structure for future subtask integration
    comments: List[dict] = []  # Structure for future comment integration
    created_at: datetime
    updated_at: Optional[datetime] = None