from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
import enum
import uuid

class InviteStatus(str, enum.Enum):
    """Invite status enum matching the model."""
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class ProjectInviteBase(BaseModel):
    """Base schema for project invite."""
    email: EmailStr


class ProjectInviteCreate(ProjectInviteBase):
    """Schema for creating a project invite."""
    pass


class ProjectInviteResponse(BaseModel):
    """Schema for project invite response."""
    id: uuid.UUID
    project_id: uuid.UUID
    email: str
    invited_by: uuid.UUID
    status: InviteStatus
    expired_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectInviteDetailResponse(ProjectInviteResponse):
    """Extended response with additional details."""
    token: Optional[str] = None  # Only include token in specific cases (e.g., for the inviter)


class ProjectInviteAcceptResponse(BaseModel):
    """Schema for accept invitation response."""
    success: bool
    message: str
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str


class ProjectInviteRejectResponse(BaseModel):
    """Schema for reject invitation response."""
    success: bool
    message: str
    status: InviteStatus


class ProjectInvitePublicResponse(BaseModel):
    """Public schema for viewing invitation details (without sensitive info)."""
    email: str
    project_name: Optional[str] = None
    status: InviteStatus
    expired_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

