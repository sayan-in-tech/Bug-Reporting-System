"""Project service for project management operations."""

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.issue import Issue
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectQueryParams, ProjectUpdate


class ProjectService:
    """Service for project operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: uuid.UUID) -> Optional[Project]:
        """Get project by ID with related data."""
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.creator))
            .options(selectinload(Project.issues))
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, project_id: uuid.UUID) -> Project:
        """Get project by ID or raise NotFoundError."""
        project = await self.get_by_id(project_id)
        if not project:
            raise NotFoundError(resource="Project")
        return project

    async def get_by_name(self, name: str) -> Optional[Project]:
        """Get project by name."""
        result = await self.db.execute(
            select(Project).where(Project.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, data: ProjectCreate, creator: User) -> Project:
        """
        Create a new project.

        Args:
            data: Project creation data
            creator: User creating the project

        Returns:
            Created project

        Raises:
            ConflictError: If project name already exists
        """
        # Check if name exists
        existing = await self.get_by_name(data.name)
        if existing:
            raise ConflictError(message="Project with this name already exists")

        project = Project(
            name=data.name,
            description=data.description,
            created_by_id=creator.id,
        )

        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)

        # Load relationships
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.creator))
            .options(selectinload(Project.issues))
            .where(Project.id == project.id)
        )
        return result.scalar_one()

    async def update(self, project: Project, data: ProjectUpdate) -> Project:
        """
        Update a project.

        Args:
            project: Project to update
            data: Update data

        Returns:
            Updated project

        Raises:
            ConflictError: If project name conflicts
        """
        update_data = data.model_dump(exclude_unset=True)

        # Check name uniqueness
        if "name" in update_data and update_data["name"] != project.name:
            existing = await self.get_by_name(update_data["name"])
            if existing:
                raise ConflictError(message="Project with this name already exists")

        for field, value in update_data.items():
            setattr(project, field, value)

        await self.db.flush()
        await self.db.refresh(project)

        return project

    async def archive(self, project: Project) -> Project:
        """Archive a project (soft delete)."""
        project.is_archived = True
        await self.db.flush()
        return project

    async def unarchive(self, project: Project) -> Project:
        """Unarchive a project."""
        project.is_archived = False
        await self.db.flush()
        return project

    async def list_projects(
        self,
        params: ProjectQueryParams,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Project], int]:
        """
        List projects with filters and pagination.

        Returns:
            Tuple of (projects list, total count)
        """
        query = select(Project).options(
            selectinload(Project.creator),
            selectinload(Project.issues),
        )

        # Apply filters
        if params.is_archived is not None:
            query = query.where(Project.is_archived == params.is_archived)

        if params.search:
            search_term = f"%{params.search}%"
            query = query.where(
                or_(
                    Project.name.ilike(search_term),
                    Project.description.ilike(search_term),
                )
            )

        # Get total count
        count_query = select(func.count(Project.id))
        if params.is_archived is not None:
            count_query = count_query.where(Project.is_archived == params.is_archived)
        if params.search:
            search_term = f"%{params.search}%"
            count_query = count_query.where(
                or_(
                    Project.name.ilike(search_term),
                    Project.description.ilike(search_term),
                )
            )

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_field = params.sort.lstrip("-")
        descending = params.sort.startswith("-")

        sort_column = getattr(Project, sort_field, Project.created_at)
        if descending:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        projects = list(result.scalars().all())

        return projects, total

    def can_modify(self, project: Project, user: User) -> bool:
        """Check if user can modify the project."""
        # Admin can modify any project
        if user.is_admin:
            return True
        # Manager can modify any project
        if user.is_manager:
            return True
        # Creator can modify their own project
        return project.created_by_id == user.id

    def can_archive(self, project: Project, user: User) -> bool:
        """Check if user can archive the project."""
        # Only creator or admin can archive
        if user.is_admin:
            return True
        return project.created_by_id == user.id
