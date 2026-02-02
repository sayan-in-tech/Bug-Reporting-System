"""Issue model definition."""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import GUID

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.project import Project
    from app.models.user import User


class IssueStatus(str, enum.Enum):
    """Issue status enumeration."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class IssuePriority(str, enum.Enum):
    """Issue priority enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Valid status transitions (state machine)
VALID_STATUS_TRANSITIONS: dict[IssueStatus, list[IssueStatus]] = {
    IssueStatus.OPEN: [IssueStatus.IN_PROGRESS, IssueStatus.CLOSED],
    IssueStatus.IN_PROGRESS: [IssueStatus.RESOLVED, IssueStatus.OPEN],
    IssueStatus.RESOLVED: [IssueStatus.CLOSED, IssueStatus.REOPENED],
    IssueStatus.CLOSED: [IssueStatus.REOPENED],
    IssueStatus.REOPENED: [
        IssueStatus.IN_PROGRESS,
        IssueStatus.RESOLVED,
        IssueStatus.CLOSED,
    ],
}


class Issue(Base):
    """Issue model for bug tracking."""

    __tablename__ = "issues"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Basic fields
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Status and priority
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IssueStatus.OPEN,
        index=True,
    )
    priority: Mapped[IssuePriority] = mapped_column(
        Enum(IssuePriority, name="issue_priority", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IssuePriority.MEDIUM,
        index=True,
    )

    # Project reference (cascade on delete)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reporter reference (restrict on delete - prevents user deletion if they reported issues)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Assignee reference (set null on delete)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Due date
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
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
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="issues",
        lazy="selectin",
    )
    reporter: Mapped["User"] = relationship(
        "User",
        back_populates="reported_issues",
        lazy="selectin",
        foreign_keys=[reporter_id],
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_issues",
        lazy="selectin",
        foreign_keys=[assignee_id],
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="issue",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, title={self.title}, status={self.status})>"

    @property
    def comment_count(self) -> int:
        """Get the total number of comments on the issue."""
        return len(self.comments) if self.comments else 0

    @property
    def is_critical(self) -> bool:
        """Check if the issue is critical priority."""
        return self.priority == IssuePriority.CRITICAL

    @property
    def is_open(self) -> bool:
        """Check if the issue is in an open state."""
        return self.status in (IssueStatus.OPEN, IssueStatus.REOPENED)

    @property
    def is_closed(self) -> bool:
        """Check if the issue is closed."""
        return self.status == IssueStatus.CLOSED

    def can_transition_to(self, new_status: IssueStatus) -> bool:
        """Check if transition to new status is valid."""
        return new_status in VALID_STATUS_TRANSITIONS.get(self.status, [])

    def get_valid_transitions(self) -> list[IssueStatus]:
        """Get list of valid status transitions from current status."""
        return VALID_STATUS_TRANSITIONS.get(self.status, [])
