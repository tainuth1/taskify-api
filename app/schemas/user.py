from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=5, max_length=50)

    @field_validator("username")
    def no_space(cls, username):
        if " " in username:
            raise ValueError("Username cannot contain spaces")
        return username

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile: Optional[str] = None

class User(UserBase):
    id: uuid.UUID
    full_name: Optional[str] = None
    profile: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True