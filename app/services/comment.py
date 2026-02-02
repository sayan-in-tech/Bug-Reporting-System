"""Comment service for comment management operations."""

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.comment import Comment
from app.models.issue import Issue
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate


class CommentService:
    """Service for comment operations.

    Note: Comments cannot be deleted to maintain audit trail.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, comment_id: uuid.UUID) -> Optional[Comment]:
        """Get comment by ID with related data."""
        result = await self.db.execute(
            select(Comment)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.issue),
            )
            .where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, comment_id: uuid.UUID) -> Comment:
        """Get comment by ID or raise NotFoundError."""
        comment = await self.get_by_id(comment_id)
        if not comment:
            raise NotFoundError(resource="Comment")
        return comment

    async def create(
        self,
        data: CommentCreate,
        issue: Issue,
        author: User,
    ) -> Comment:
        """
        Create a new comment on an issue.

        Args:
            data: Comment creation data
            issue: Issue to comment on
            author: User creating the comment

        Returns:
            Created comment
        """
        comment = Comment(
            content=data.content,
            issue_id=issue.id,
            author_id=author.id,
        )

        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)

        # Load relationships
        result = await self.db.execute(
            select(Comment)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.issue),
            )
            .where(Comment.id == comment.id)
        )
        return result.scalar_one()

    async def update(self, comment: Comment, data: CommentUpdate) -> Comment:
        """
        Update a comment.

        Args:
            comment: Comment to update
            data: Update data

        Returns:
            Updated comment

        Note: Only the author can update their own comments.
        """
        comment.content = data.content
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def list_comments(
        self,
        issue_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Comment], int]:
        """
        List comments for an issue with pagination.

        Returns:
            Tuple of (comments list, total count)
        """
        query = select(Comment).options(
            selectinload(Comment.author),
        ).where(Comment.issue_id == issue_id)

        # Get total count
        count_query = select(func.count(Comment.id)).where(
            Comment.issue_id == issue_id
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination and ordering (oldest first for comments)
        query = query.order_by(Comment.created_at.asc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        comments = list(result.scalars().all())

        return comments, total

    def can_modify(self, comment: Comment, user: User) -> bool:
        """Check if user can modify the comment."""
        # Admin can modify any comment
        if user.is_admin:
            return True
        # Only author can modify their own comment
        return comment.author_id == user.id

    # Note: No delete method - comments cannot be deleted for audit trail
