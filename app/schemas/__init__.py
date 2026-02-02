"""Pydantic schemas for request/response validation."""

from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.comment import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
)
from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
)
from app.schemas.issue import (
    IssueCreate,
    IssueResponse,
    IssueUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # Auth
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    # User
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Project
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # Issue
    "IssueCreate",
    "IssueResponse",
    "IssueUpdate",
    # Comment
    "CommentCreate",
    "CommentResponse",
    "CommentUpdate",
    # Common
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
]
