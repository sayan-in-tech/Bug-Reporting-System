"""User schemas for request/response validation."""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    """Base user schema."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username (alphanumeric, underscores, and hyphens only)",
    )
    email: EmailStr = Field(..., description="Valid email address")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must include uppercase, lowercase, digit, and special char)",
    )
    role: UserRole = Field(
        default=UserRole.DEVELOPER,
        description="User role",
    )

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password complexity requirements."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserUpdate(BaseSchema):
    """Schema for updating a user."""

    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseSchema):
    """Schema for user response."""

    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserSummary(BaseSchema):
    """Minimal user summary for embedding in other responses."""

    id: uuid.UUID
    username: str
    email: str
    role: UserRole
