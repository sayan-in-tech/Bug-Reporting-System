"""User service for user management operations."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for user operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, user_id: uuid.UUID) -> User:
        """Get user by ID or raise NotFoundError."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError(resource="User")
        return user

    async def create(self, data: UserCreate) -> User:
        """
        Create a new user.

        Args:
            data: User creation data

        Returns:
            Created user

        Raises:
            ValidationError: If username or email already exists
        """
        # Check if username exists
        if await self.get_by_username(data.username):
            raise ValidationError(
                message="Username already exists",
                details=[{"field": "username", "message": "This username is already taken"}],
            )

        # Check if email exists
        if await self.get_by_email(data.email):
            raise ValidationError(
                message="Email already exists",
                details=[{"field": "email", "message": "This email is already registered"}],
            )

        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update(self, user: User, data: UserUpdate) -> User:
        """
        Update a user.

        Args:
            user: User to update
            data: Update data

        Returns:
            Updated user

        Raises:
            ConflictError: If username or email conflicts
        """
        update_data = data.model_dump(exclude_unset=True)

        # Check username uniqueness
        if "username" in update_data and update_data["username"] != user.username:
            existing = await self.get_by_username(update_data["username"])
            if existing:
                raise ConflictError(message="Username already exists")

        # Check email uniqueness
        if "email" in update_data and update_data["email"] != user.email:
            existing = await self.get_by_email(update_data["email"])
            if existing:
                raise ConflictError(message="Email already exists")

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def deactivate(self, user: User) -> User:
        """Deactivate a user account."""
        user.is_active = False
        await self.db.flush()
        return user

    async def activate(self, user: User) -> User:
        """Activate a user account."""
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.flush()
        return user

    async def list_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """
        List users with optional filters.

        Returns:
            Tuple of (users list, total count)
        """
        query = select(User)

        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # Get total count
        count_query = select(User.id)
        if role is not None:
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            count_query = count_query.where(User.is_active == is_active)

        count_result = await self.db.execute(count_query)
        total = len(count_result.all())

        # Get paginated results
        query = query.offset(offset).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total
