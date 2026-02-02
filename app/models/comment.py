"""Comment model definition."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.issue import Issue
    from app.models.user import User


class Comment(Base):
    """Comment model for issue discussions.

    Note: Comments cannot be deleted to maintain audit trail.
    """

    __tablename__ = "comments"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Content (required, max 2000 chars enforced at schema level)
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Issue reference (cascade on delete)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Author reference (restrict on delete - prevents user deletion if they authored comments)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    issue: Mapped["Issue"] = relationship(
        "Issue",
        back_populates="comments",
        lazy="selectin",
    )
    author: Mapped["User"] = relationship(
        "User",
        back_populates="comments",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, issue_id={self.issue_id}, author_id={self.author_id})>"

    @property
    def is_edited(self) -> bool:
        """Check if the comment has been edited."""
        # Allow for small time differences due to database precision
        if self.updated_at and self.created_at:
            diff = (self.updated_at - self.created_at).total_seconds()
            return diff > 1
        return False
