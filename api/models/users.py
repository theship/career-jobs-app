"""
User models for database and API
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model"""

    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UserCreate(UserBase):
    """Model for creating a new user"""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Model for updating user information"""

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UserInDB(UserBase):
    """User model as stored in database"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    email_verified: bool = False

    class Config:
        orm_mode = True


class UserResponse(BaseModel):
    """User model for API responses"""

    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    is_active: bool = True
    email_verified: bool = False

    class Config:
        orm_mode = True


class UserProfile(BaseModel):
    """Extended user profile"""

    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    resume_count: int = 0
    job_matches_count: int = 0

    class Config:
        orm_mode = True
