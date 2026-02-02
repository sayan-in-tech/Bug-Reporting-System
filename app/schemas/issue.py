"""Issue schemas for request/response validation."""

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from app.models.issue import IssuePriority, IssueStatus
from app.schemas.common import BaseSchema
from app.schemas.project import ProjectSummary
from app.schemas.user import UserSummary
from app.utils.markdown_sanitizer import sanitize_markdown


class IssueBase(BaseSchema):
    """Base issue schema."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Issue title",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Issue description (markdown supported, max 5000 chars)",
    )
    priority: IssuePriority = Field(
        default=IssuePriority.MEDIUM,
        description="Issue priority",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Due date (optional)",
    )


class IssueCreate(IssueBase):
    """Schema for creating a new issue."""

    assignee_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Assignee user ID (optional)",
    )

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize markdown description to prevent XSS."""
        if v is None:
            return None
        return sanitize_markdown(v)


class IssueUpdate(BaseSchema):
    """Schema for updating an issue."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
    )
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize markdown description to prevent XSS."""
        if v is None:
            return None
        return sanitize_markdown(v)


class IssueResponse(BaseSchema):
    """Schema for issue response."""

    id: uuid.UUID
    title: str
    description: Optional[str]
    status: IssueStatus
    priority: IssuePriority
    project: ProjectSummary
    reporter: UserSummary
    assignee: Optional[UserSummary]
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    comment_count: int = Field(default=0, description="Number of comments")


class IssueSummary(BaseSchema):
    """Minimal issue summary for embedding in other responses."""

    id: uuid.UUID
    title: str
    status: IssueStatus
    priority: IssuePriority


class IssueQueryParams(BaseSchema):
    """Query parameters for issue list endpoint."""

    status: Optional[IssueStatus] = Field(
        default=None,
        description="Filter by status",
    )
    priority: Optional[IssuePriority] = Field(
        default=None,
        description="Filter by priority",
    )
    assignee: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter by assignee ID",
    )
    reporter: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter by reporter ID",
    )
    search: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Search in issue title and description",
    )
    sort: Literal[
        "title", "-title",
        "created_at", "-created_at",
        "updated_at", "-updated_at",
        "priority", "-priority",
        "due_date", "-due_date"
    ] = Field(
        default="-created_at",
        description="Sort order (prefix with - for descending)",
    )

    @field_validator("search")
    @classmethod
    def sanitize_search(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize search input."""
        if v is None:
            return None
        v = v.strip()[:100]
        return "".join(c for c in v if c.isalnum() or c in " -_")


class IssueStatusTransition(BaseSchema):
    """Schema for status transition information."""

    current_status: IssueStatus
    valid_transitions: list[IssueStatus]
