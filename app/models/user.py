"""User model definition."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.issue import Issue
    from app.models.project import Project


class UserRole(str, enum.Enum):
    """User roles enumeration."""

    DEVELOPER = "developer"
    MANAGER = "manager"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Basic fields
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Role and status
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.DEVELOPER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Account lockout fields
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    created_projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="creator",
        lazy="selectin",
        foreign_keys="Project.created_by_id",
    )
    reported_issues: Mapped[list["Issue"]] = relationship(
        "Issue",
        back_populates="reporter",
        lazy="selectin",
        foreign_keys="Issue.reporter_id",
    )
    assigned_issues: Mapped[list["Issue"]] = relationship(
        "Issue",
        back_populates="assignee",
        lazy="selectin",
        foreign_keys="Issue.assignee_id",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

    @property
    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        """Check if user is a manager or admin."""
        return self.role in (UserRole.MANAGER, UserRole.ADMIN)

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.now(self.locked_until.tzinfo) < self.locked_until
