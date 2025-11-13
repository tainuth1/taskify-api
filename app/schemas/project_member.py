from pydantic import BaseModel
from datetime import datetime
import uuid
import enum

from app.models.project_member import MemberRole as MemberRoleModel
from app.schemas.user import User

class MemberRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"

class MemberRoleUpdate(BaseModel):
    project_id: uuid.UUID
    member_id: uuid.UUID  # The ID of the ProjectMember record not user_id
    role: MemberRole

    class Config:
        from_attributes = True

class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    role: str
    status: str

    class Config:
        from_attributes = True

class ProjectMemberDetailResponse(BaseModel):
    id: uuid.UUID
    user: User
    role: str
    status: str
    join_at: datetime
    left_at: datetime | None = None

    class Config:
        from_attributes = True

class MemberRemoveRequest(BaseModel):
    project_id: uuid.UUID
    member_id: uuid.UUID  # The ID of the ProjectMember record not user_id

    class Config:
        from_attributes = True
