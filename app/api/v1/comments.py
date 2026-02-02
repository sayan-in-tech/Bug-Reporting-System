"""Comment API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_permission
from app.core.exceptions import AuthorizationError
from app.core.permissions import Permission
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserSummary
from app.services.comment import CommentService
from app.services.issue import IssueService

router = APIRouter()


def _comment_to_response(comment) -> CommentResponse:
    """Convert comment model to response schema."""
    return CommentResponse(
        id=comment.id,
        content=comment.content,
        issue_id=comment.issue_id,
        author=UserSummary(
            id=comment.author.id,
            username=comment.author.username,
            email=comment.author.email,
            role=comment.author.role,
        ),
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=comment.is_edited,
    )


@router.get(
    "/issues/{issue_id}/comments",
    response_model=PaginatedResponse[CommentResponse],
    summary="List comments on an issue",
    description="Get a paginated list of comments for a specific issue.",
    dependencies=[Depends(require_permission(Permission.VIEW_COMMENTS))],
)
async def list_comments(
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[CommentResponse]:
    """List comments for an issue with pagination."""
    # Verify issue exists
    issue_service = IssueService(db)
    await issue_service.get_or_404(issue_id)

    comment_service = CommentService(db)

    offset = (page - 1) * limit
    comments, total = await comment_service.list_comments(
        issue_id=issue_id,
        offset=offset,
        limit=limit,
    )

    return PaginatedResponse.create(
        items=[_comment_to_response(c) for c in comments],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/issues/{issue_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment to an issue",
    description="Create a new comment on an issue.",
    dependencies=[Depends(require_permission(Permission.ADD_COMMENT))],
)
async def create_comment(
    issue_id: uuid.UUID,
    data: CommentCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CommentResponse:
    """Create a new comment on an issue."""
    # Get issue
    issue_service = IssueService(db)
    issue = await issue_service.get_or_404(issue_id)

    # Create comment
    comment_service = CommentService(db)
    comment = await comment_service.create(data, issue, current_user)

    return _comment_to_response(comment)


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Update a comment",
    description="Update a comment. Only the author can update their own comments.",
)
async def update_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> CommentResponse:
    """Update a comment. Only the author can update."""
    comment_service = CommentService(db)
    comment = await comment_service.get_or_404(comment_id)

    # Check permission - only author can update
    if not comment_service.can_modify(comment, current_user):
        raise AuthorizationError(
            message="Only the comment author can update this comment"
        )

    comment = await comment_service.update(comment, data)
    return _comment_to_response(comment)


# Note: No DELETE endpoint for comments - they cannot be deleted to maintain audit trail
