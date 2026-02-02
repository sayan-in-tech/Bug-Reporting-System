"""Issue service for issue management operations."""

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.models.issue import (
    Issue,
    IssuePriority,
    IssueStatus,
    VALID_STATUS_TRANSITIONS,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueQueryParams, IssueUpdate


class IssueService:
    """Service for issue operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, issue_id: uuid.UUID) -> Optional[Issue]:
        """Get issue by ID with related data."""
        result = await self.db.execute(
            select(Issue)
            .options(
                selectinload(Issue.project),
                selectinload(Issue.reporter),
                selectinload(Issue.assignee),
                selectinload(Issue.comments),
            )
            .where(Issue.id == issue_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, issue_id: uuid.UUID) -> Issue:
        """Get issue by ID or raise NotFoundError."""
        issue = await self.get_by_id(issue_id)
        if not issue:
            raise NotFoundError(resource="Issue")
        return issue

    async def create(
        self,
        data: IssueCreate,
        project: Project,
        reporter: User,
    ) -> Issue:
        """
        Create a new issue.

        Args:
            data: Issue creation data
            project: Project to create issue in
            reporter: User reporting the issue

        Returns:
            Created issue
        """
        issue = Issue(
            title=data.title,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            project_id=project.id,
            reporter_id=reporter.id,
            assignee_id=data.assignee_id,
            status=IssueStatus.OPEN,
        )

        self.db.add(issue)
        await self.db.flush()
        await self.db.refresh(issue)

        # Load relationships
        result = await self.db.execute(
            select(Issue)
            .options(
                selectinload(Issue.project),
                selectinload(Issue.reporter),
                selectinload(Issue.assignee),
                selectinload(Issue.comments),
            )
            .where(Issue.id == issue.id)
        )
        return result.scalar_one()

    async def update(
        self,
        issue: Issue,
        data: IssueUpdate,
        current_user: User,
    ) -> Issue:
        """
        Update an issue.

        Args:
            issue: Issue to update
            data: Update data
            current_user: User performing the update

        Returns:
            Updated issue

        Raises:
            InvalidStatusTransitionError: If status transition is invalid
            BusinessRuleError: If business rules are violated
        """
        update_data = data.model_dump(exclude_unset=True)

        # Handle status transition
        if "status" in update_data:
            new_status = update_data["status"]
            await self._validate_status_transition(issue, new_status)

        for field, value in update_data.items():
            setattr(issue, field, value)

        await self.db.flush()
        await self.db.refresh(issue)

        return issue

    async def _validate_status_transition(
        self,
        issue: Issue,
        new_status: IssueStatus,
    ) -> None:
        """
        Validate status transition and business rules.

        Args:
            issue: Current issue
            new_status: Target status

        Raises:
            InvalidStatusTransitionError: If transition is invalid
            BusinessRuleError: If business rules are violated
        """
        # Check valid transition
        if not issue.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                current_status=issue.status.value,
                target_status=new_status.value,
                valid_transitions=[s.value for s in issue.get_valid_transitions()],
            )

        # Business rule: Critical issues cannot be closed without a comment
        if (
            new_status == IssueStatus.CLOSED
            and issue.priority == IssuePriority.CRITICAL
            and issue.comment_count == 0
        ):
            raise BusinessRuleError(
                message="Critical issues cannot be closed without at least one comment",
                code="CRITICAL_ISSUE_REQUIRES_COMMENT",
            )

    async def list_issues(
        self,
        project_id: uuid.UUID,
        params: IssueQueryParams,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Issue], int]:
        """
        List issues for a project with filters and pagination.

        Returns:
            Tuple of (issues list, total count)
        """
        query = select(Issue).options(
            selectinload(Issue.project),
            selectinload(Issue.reporter),
            selectinload(Issue.assignee),
            selectinload(Issue.comments),
        ).where(Issue.project_id == project_id)

        # Apply filters
        if params.status is not None:
            query = query.where(Issue.status == params.status)

        if params.priority is not None:
            query = query.where(Issue.priority == params.priority)

        if params.assignee is not None:
            query = query.where(Issue.assignee_id == params.assignee)

        if params.reporter is not None:
            query = query.where(Issue.reporter_id == params.reporter)

        if params.search:
            search_term = f"%{params.search}%"
            query = query.where(
                or_(
                    Issue.title.ilike(search_term),
                    Issue.description.ilike(search_term),
                )
            )

        # Get total count
        count_query = select(func.count(Issue.id)).where(Issue.project_id == project_id)
        if params.status is not None:
            count_query = count_query.where(Issue.status == params.status)
        if params.priority is not None:
            count_query = count_query.where(Issue.priority == params.priority)
        if params.assignee is not None:
            count_query = count_query.where(Issue.assignee_id == params.assignee)
        if params.reporter is not None:
            count_query = count_query.where(Issue.reporter_id == params.reporter)
        if params.search:
            search_term = f"%{params.search}%"
            count_query = count_query.where(
                or_(
                    Issue.title.ilike(search_term),
                    Issue.description.ilike(search_term),
                )
            )

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_field = params.sort.lstrip("-")
        descending = params.sort.startswith("-")

        # Map sort field to column
        sort_mapping = {
            "title": Issue.title,
            "created_at": Issue.created_at,
            "updated_at": Issue.updated_at,
            "priority": Issue.priority,
            "due_date": Issue.due_date,
        }
        sort_column = sort_mapping.get(sort_field, Issue.created_at)

        if descending:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        issues = list(result.scalars().all())

        return issues, total

    def can_modify(self, issue: Issue, user: User) -> bool:
        """Check if user can modify the issue."""
        # Admin can modify any issue
        if user.is_admin:
            return True
        # Manager can modify any issue
        if user.is_manager:
            return True
        # Reporter can modify their issue
        if issue.reporter_id == user.id:
            return True
        # Assignee can modify their issue
        if issue.assignee_id == user.id:
            return True
        return False

    def can_change_assignee(self, issue: Issue, user: User) -> bool:
        """Check if user can change the assignee."""
        # Admin can change assignee
        if user.is_admin:
            return True
        # Manager can change assignee
        if user.is_manager:
            return True
        # Reporter can change assignee
        if issue.reporter_id == user.id:
            return True
        return False
