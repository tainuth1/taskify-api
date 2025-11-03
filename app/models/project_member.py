from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Enum as SqlEnum
import uuid
import enum
from app.database import Base

class MemberRole(enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"

class MemberStatus(enum.Enum):
    active = "active"
    left = "left"
    remove = "remove"

class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(SqlEnum(MemberRole, name="member_role"), nullable=False, default=MemberRole.member)
    status = Column(SqlEnum(MemberStatus, name="member_status"), nullable=False, default=MemberStatus.active)
    join_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)