"""Project schemas for request/response validation."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema
from app.schemas.user import UserSummary


class ProjectBase(BaseSchema):
    """Base project schema."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Project name (unique)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Project description (optional, max 1000 chars)",
    )


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseSchema):
    """Schema for updating a project."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
    )
    is_archived: Optional[bool] = None


class ProjectResponse(BaseSchema):
    """Schema for project response."""

    id: uuid.UUID
    name: str
    description: Optional[str]
    created_by: UserSummary
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    issue_count: int = Field(default=0, description="Total number of issues")
    open_issue_count: int = Field(default=0, description="Number of open issues")


class ProjectSummary(BaseSchema):
    """Minimal project summary for embedding in other responses."""

    id: uuid.UUID
    name: str
    is_archived: bool


class ProjectQueryParams(BaseSchema):
    """Query parameters for project list endpoint."""

    search: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Search in project name and description",
    )
    is_archived: Optional[bool] = Field(
        default=None,
        description="Filter by archived status",
    )
    sort: Literal["name", "-name", "created_at", "-created_at", "updated_at", "-updated_at"] = Field(
        default="-created_at",
        description="Sort order (prefix with - for descending)",
    )

    @field_validator("search")
    @classmethod
    def sanitize_search(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize search input."""
        if v is None:
            return None
        # Strip whitespace and limit length
        v = v.strip()[:100]
        # Remove potentially dangerous characters
        return "".join(c for c in v if c.isalnum() or c in " -_")
