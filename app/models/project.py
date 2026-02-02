"""Project model definition."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.issue import Issue
    from app.models.user import User


class Project(Base):
    """Project model for organizing issues."""

    __tablename__ = "projects"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Basic fields
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Creator reference (protect on delete)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="PROTECT"),
        nullable=False,
        index=True,
    )

    # Soft delete flag
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_projects",
        lazy="selectin",
    )
    issues: Mapped[list["Issue"]] = relationship(
        "Issue",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, archived={self.is_archived})>"

    @property
    def issue_count(self) -> int:
        """Get the total number of issues in the project."""
        return len(self.issues) if self.issues else 0

    @property
    def open_issue_count(self) -> int:
        """Get the number of open issues in the project."""
        if not self.issues:
            return 0
        from app.models.issue import IssueStatus
        return sum(1 for issue in self.issues if issue.status == IssueStatus.OPEN)
