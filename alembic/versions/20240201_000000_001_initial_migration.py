"""Initial migration - create all tables.

Revision ID: 001
Revises: None
Create Date: 2024-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all database tables."""
    # Create user_role enum
    user_role_enum = postgresql.ENUM(
        "developer", "manager", "admin",
        name="user_role",
        create_type=True,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # Create issue_status enum
    issue_status_enum = postgresql.ENUM(
        "open", "in_progress", "resolved", "closed", "reopened",
        name="issue_status",
        create_type=True,
    )
    issue_status_enum.create(op.get_bind(), checkfirst=True)

    # Create issue_priority enum
    issue_priority_enum = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="issue_priority",
        create_type=True,
    )
    issue_priority_enum.create(op.get_bind(), checkfirst=True)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("developer", "manager", "admin", name="user_role", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, default=0),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="PROTECT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_created_by_id", "projects", ["created_by_id"])
    op.create_index("ix_projects_is_archived", "projects", ["is_archived"])

    # Create issues table
    op.create_table(
        "issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("open", "in_progress", "resolved", "closed", "reopened", name="issue_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM("low", "medium", "high", "critical", name="issue_priority", create_type=False),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="PROTECT"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issues_id", "issues", ["id"])
    op.create_index("ix_issues_title", "issues", ["title"])
    op.create_index("ix_issues_status", "issues", ["status"])
    op.create_index("ix_issues_priority", "issues", ["priority"])
    op.create_index("ix_issues_project_id", "issues", ["project_id"])
    op.create_index("ix_issues_reporter_id", "issues", ["reporter_id"])
    op.create_index("ix_issues_assignee_id", "issues", ["assignee_id"])

    # Create comments table
    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="PROTECT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_id", "comments", ["id"])
    op.create_index("ix_comments_issue_id", "comments", ["issue_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])


def downgrade() -> None:
    """Drop all database tables."""
    # Drop tables in reverse order (respect foreign keys)
    op.drop_index("ix_comments_author_id", "comments")
    op.drop_index("ix_comments_issue_id", "comments")
    op.drop_index("ix_comments_id", "comments")
    op.drop_table("comments")

    op.drop_index("ix_issues_assignee_id", "issues")
    op.drop_index("ix_issues_reporter_id", "issues")
    op.drop_index("ix_issues_project_id", "issues")
    op.drop_index("ix_issues_priority", "issues")
    op.drop_index("ix_issues_status", "issues")
    op.drop_index("ix_issues_title", "issues")
    op.drop_index("ix_issues_id", "issues")
    op.drop_table("issues")

    op.drop_index("ix_projects_is_archived", "projects")
    op.drop_index("ix_projects_created_by_id", "projects")
    op.drop_index("ix_projects_name", "projects")
    op.drop_index("ix_projects_id", "projects")
    op.drop_table("projects")

    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")

    # Drop enums
    postgresql.ENUM(name="issue_priority").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="issue_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
