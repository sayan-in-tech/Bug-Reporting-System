"""Issue API endpoints."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_permission
from app.core.exceptions import AuthorizationError
from app.core.permissions import Permission
from app.models.issue import IssuePriority, IssueStatus
from app.schemas.common import PaginatedResponse
from app.schemas.issue import (
    IssueCreate,
    IssueQueryParams,
    IssueResponse,
    IssueStatusTransition,
    IssueUpdate,
)
from app.schemas.project import ProjectSummary
from app.schemas.user import UserSummary
from app.services.issue import IssueService
from app.services.project import ProjectService

router = APIRouter()


def _issue_to_response(issue) -> IssueResponse:
    """Convert issue model to response schema."""
    return IssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        priority=issue.priority,
        project=ProjectSummary(
            id=issue.project.id,
            name=issue.project.name,
            is_archived=issue.project.is_archived,
        ),
        reporter=UserSummary(
            id=issue.reporter.id,
            username=issue.reporter.username,
            email=issue.reporter.email,
            role=issue.reporter.role,
        ),
        assignee=UserSummary(
            id=issue.assignee.id,
            username=issue.assignee.username,
            email=issue.assignee.email,
            role=issue.assignee.role,
        ) if issue.assignee else None,
        due_date=issue.due_date,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        comment_count=issue.comment_count,
    )


@router.get(
    "/projects/{project_id}/issues",
    response_model=PaginatedResponse[IssueResponse],
    summary="List issues in a project",
    description="Get a paginated list of issues for a specific project with optional filters.",
    dependencies=[Depends(require_permission(Permission.VIEW_ISSUES))],
)
async def list_issues(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    status: Annotated[Optional[IssueStatus], Query()] = None,
    priority: Annotated[Optional[IssuePriority], Query()] = None,
    assignee: Annotated[Optional[uuid.UUID], Query()] = None,
    reporter: Annotated[Optional[uuid.UUID], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    sort: Annotated[str, Query()] = "-created_at",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[IssueResponse]:
    """List issues for a project with filters and pagination."""
    # Verify project exists
    project_service = ProjectService(db)
    await project_service.get_or_404(project_id)

    issue_service = IssueService(db)

    params = IssueQueryParams(
        status=status,
        priority=priority,
        assignee=assignee,
        reporter=reporter,
        search=search,
        sort=sort,
    )

    offset = (page - 1) * limit
    issues, total = await issue_service.list_issues(
        project_id=project_id,
        params=params,
        offset=offset,
        limit=limit,
    )

    return PaginatedResponse.create(
        items=[_issue_to_response(i) for i in issues],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/projects/{project_id}/issues",
    response_model=IssueResponse,
    status_code=201,
    summary="Create a new issue",
    description="Create a new issue in a project.",
    dependencies=[Depends(require_permission(Permission.CREATE_ISSUE))],
)
async def create_issue(
    project_id: uuid.UUID,
    data: IssueCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> IssueResponse:
    """Create a new issue in a project."""
    # Get project
    project_service = ProjectService(db)
    project = await project_service.get_or_404(project_id)

    # Create issue
    issue_service = IssueService(db)
    issue = await issue_service.create(data, project, current_user)

    return _issue_to_response(issue)


@router.get(
    "/issues/{issue_id}",
    response_model=IssueResponse,
    summary="Get issue details",
    description="Get detailed information about a specific issue.",
    dependencies=[Depends(require_permission(Permission.VIEW_ISSUES))],
)
async def get_issue(
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> IssueResponse:
    """Get an issue by ID."""
    issue_service = IssueService(db)
    issue = await issue_service.get_or_404(issue_id)
    return _issue_to_response(issue)


@router.patch(
    "/issues/{issue_id}",
    response_model=IssueResponse,
    summary="Update an issue",
    description="Update issue details. Reporter, assignee, or admin can modify.",
)
async def update_issue(
    issue_id: uuid.UUID,
    data: IssueUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> IssueResponse:
    """Update an issue."""
    issue_service = IssueService(db)
    issue = await issue_service.get_or_404(issue_id)

    # Check general modification permission
    if not issue_service.can_modify(issue, current_user):
        raise AuthorizationError(
            message="Only the reporter, assignee, or admin can modify this issue"
        )

    # Check assignee change permission
    if data.assignee_id is not None and data.assignee_id != issue.assignee_id:
        if not issue_service.can_change_assignee(issue, current_user):
            raise AuthorizationError(
                message="Only the reporter, manager, or admin can change the assignee"
            )

    issue = await issue_service.update(issue, data, current_user)
    return _issue_to_response(issue)


@router.get(
    "/issues/{issue_id}/transitions",
    response_model=IssueStatusTransition,
    summary="Get valid status transitions",
    description="Get the valid status transitions for an issue based on its current status.",
    dependencies=[Depends(require_permission(Permission.VIEW_ISSUES))],
)
async def get_issue_transitions(
    issue_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> IssueStatusTransition:
    """Get valid status transitions for an issue."""
    issue_service = IssueService(db)
    issue = await issue_service.get_or_404(issue_id)

    return IssueStatusTransition(
        current_status=issue.status,
        valid_transitions=issue.get_valid_transitions(),
    )
