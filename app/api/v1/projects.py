"""Project API endpoints."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_permission
from app.core.exceptions import AuthorizationError
from app.core.permissions import Permission
from app.schemas.common import PaginatedResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectQueryParams,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.user import UserSummary
from app.services.project import ProjectService

router = APIRouter()


def _project_to_response(project) -> ProjectResponse:
    """Convert project model to response schema."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_by=UserSummary(
            id=project.creator.id,
            username=project.creator.username,
            email=project.creator.email,
            role=project.creator.role,
        ),
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        issue_count=project.issue_count,
        open_issue_count=project.open_issue_count,
    )


@router.get(
    "",
    response_model=PaginatedResponse[ProjectResponse],
    summary="List all projects",
    description="Get a paginated list of projects with optional filters.",
    dependencies=[Depends(require_permission(Permission.VIEW_PROJECTS))],
)
async def list_projects(
    current_user: CurrentUser,
    db: DbSession,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    is_archived: Annotated[Optional[bool], Query()] = None,
    sort: Annotated[str, Query()] = "-created_at",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[ProjectResponse]:
    """List all projects with filters and pagination."""
    project_service = ProjectService(db)

    params = ProjectQueryParams(
        search=search,
        is_archived=is_archived,
        sort=sort,
    )

    offset = (page - 1) * limit
    projects, total = await project_service.list_projects(
        params=params,
        offset=offset,
        limit=limit,
    )

    return PaginatedResponse.create(
        items=[_project_to_response(p) for p in projects],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=201,
    summary="Create a new project",
    description="Create a new project. Requires manager or admin role.",
    dependencies=[Depends(require_permission(Permission.CREATE_PROJECT))],
)
async def create_project(
    data: ProjectCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ProjectResponse:
    """Create a new project."""
    project_service = ProjectService(db)
    project = await project_service.create(data, current_user)
    return _project_to_response(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    description="Get detailed information about a specific project.",
    dependencies=[Depends(require_permission(Permission.VIEW_PROJECTS))],
)
async def get_project(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ProjectResponse:
    """Get a project by ID."""
    project_service = ProjectService(db)
    project = await project_service.get_or_404(project_id)
    return _project_to_response(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    description="Update project details. Only project owner or admin can modify.",
)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ProjectResponse:
    """Update a project."""
    project_service = ProjectService(db)
    project = await project_service.get_or_404(project_id)

    # Check permission
    if not project_service.can_modify(project, current_user):
        raise AuthorizationError(
            message="Only the project owner or admin can modify this project"
        )

    # Check archive permission
    if data.is_archived is not None and not project_service.can_archive(project, current_user):
        raise AuthorizationError(
            message="Only the project creator or admin can archive this project"
        )

    project = await project_service.update(project, data)
    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Archive a project",
    description="Archive a project (soft delete). Only project owner or admin can archive.",
)
async def archive_project(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ProjectResponse:
    """Archive a project (soft delete)."""
    project_service = ProjectService(db)
    project = await project_service.get_or_404(project_id)

    # Check permission
    if not project_service.can_archive(project, current_user):
        raise AuthorizationError(
            message="Only the project creator or admin can archive this project"
        )

    project = await project_service.archive(project)
    return _project_to_response(project)
