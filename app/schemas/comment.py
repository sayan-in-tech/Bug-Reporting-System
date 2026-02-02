"""Comment schemas for request/response validation."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema
from app.schemas.user import UserSummary
from app.utils.markdown_sanitizer import sanitize_markdown


class CommentBase(BaseSchema):
    """Base comment schema."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Comment content (required, max 2000 chars)",
    )


class CommentCreate(CommentBase):
    """Schema for creating a new comment."""

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize comment content to prevent XSS."""
        return sanitize_markdown(v)


class CommentUpdate(BaseSchema):
    """Schema for updating a comment.

    Note: Only the author can update their own comments.
    Comments cannot be deleted to maintain audit trail.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Updated comment content",
    )

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize comment content to prevent XSS."""
        return sanitize_markdown(v)


class CommentResponse(BaseSchema):
    """Schema for comment response."""

    id: uuid.UUID
    content: str
    issue_id: uuid.UUID
    author: UserSummary
    created_at: datetime
    updated_at: datetime
    is_edited: bool = Field(default=False, description="Whether the comment has been edited")


class CommentSummary(BaseSchema):
    """Minimal comment summary for embedding in other responses."""

    id: uuid.UUID
    content: str
    author_id: uuid.UUID
    created_at: datetime
