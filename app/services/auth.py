"""Authentication service for handling login, logout, and token management."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis.asyncio as redis
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_session_id,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.user import User, UserRole
from app.redis import SessionStore, TokenBlacklist
from app.schemas.auth import RegisterRequest, TokenResponse


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.token_blacklist = TokenBlacklist(redis_client)
        self.session_store = SessionStore(redis_client)

    async def register(self, data: RegisterRequest) -> User:
        """
        Register a new user.

        Args:
            data: Registration data

        Returns:
            Created user

        Raises:
            ValidationError: If username or email already exists
        """
        # Check if username exists
        existing_username = await self.db.execute(
            select(User).where(User.username == data.username)
        )
        if existing_username.scalar_one_or_none():
            raise ValidationError(
                message="Username already exists",
                details=[{"field": "username", "message": "This username is already taken"}],
            )

        # Check if email exists
        existing_email = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        if existing_email.scalar_one_or_none():
            raise ValidationError(
                message="Email already exists",
                details=[{"field": "email", "message": "This email is already registered"}],
            )

        # Create user
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

    async def authenticate(self, username: str, password: str) -> tuple[User, TokenResponse]:
        """
        Authenticate a user and return tokens.

        Args:
            username: Username or email
            password: Password

        Returns:
            Tuple of (user, token response)

        Raises:
            AuthenticationError: If credentials are invalid
            AccountLockedError: If account is locked
        """
        # Find user by username or email
        result = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == username)
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError(message="Invalid credentials")

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise AccountLockedError(
                unlock_at=user.locked_until.isoformat(),
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            await self._handle_failed_login(user)
            raise AuthenticationError(message="Invalid credentials")

        # Check if account is active
        if not user.is_active:
            raise AuthenticationError(message="Account is deactivated")

        # Reset failed login attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)

        # Check if password needs rehashing
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        await self.db.flush()

        # Generate tokens
        session_id = generate_session_id()
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
            session_id=session_id,
        )
        refresh_token, refresh_jti = create_refresh_token(
            user_id=str(user.id),
            session_id=session_id,
        )

        # Store session in Redis
        await self.session_store.create(
            session_id=session_id,
            user_id=str(user.id),
            refresh_token=refresh_jti,
            expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        return user, TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Current refresh token

        Returns:
            New token response

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise AuthenticationError(message="Invalid refresh token")

        # Validate token type
        if payload.get("type") != "refresh":
            raise AuthenticationError(message="Invalid token type")

        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti and await self.token_blacklist.is_blacklisted(jti):
            raise AuthenticationError(message="Token has been revoked")

        # Get session
        session_id = payload.get("session_id")
        session = await self.session_store.get(session_id)
        if not session:
            raise AuthenticationError(message="Session expired")

        # Verify refresh token matches session
        if session.get("refresh_token") != jti:
            raise AuthenticationError(message="Invalid refresh token")

        # Get user
        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError(message="User not found or inactive")

        # Blacklist old refresh token
        exp = payload.get("exp", 0)
        remaining = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
        await self.token_blacklist.add(jti, remaining)

        # Generate new tokens (refresh token rotation)
        new_session_id = generate_session_id()
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
            session_id=new_session_id,
        )
        new_refresh_token, new_refresh_jti = create_refresh_token(
            user_id=str(user.id),
            session_id=new_session_id,
        )

        # Delete old session and create new one
        await self.session_store.delete(session_id)
        await self.session_store.create(
            session_id=new_session_id,
            user_id=str(user.id),
            refresh_token=new_refresh_jti,
            expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def logout(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        """
        Logout user and invalidate tokens.

        Args:
            access_token: Current access token
            refresh_token: Optional refresh token to invalidate
        """
        try:
            payload = decode_token(access_token)
            session_id = payload.get("session_id")

            # Blacklist access token
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp", 0)
                remaining = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
                await self.token_blacklist.add(jti, remaining)

            # Delete session
            if session_id:
                await self.session_store.delete(session_id)

        except JWTError:
            pass  # Token already invalid

        # Blacklist refresh token if provided
        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                refresh_jti = refresh_payload.get("jti")
                if refresh_jti:
                    exp = refresh_payload.get("exp", 0)
                    remaining = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
                    await self.token_blacklist.add(refresh_jti, remaining)
            except JWTError:
                pass

    async def logout_all_devices(self, user_id: str) -> int:
        """
        Logout user from all devices.

        Args:
            user_id: User ID

        Returns:
            Number of sessions invalidated
        """
        return await self.session_store.delete_all_user_sessions(user_id)

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """
        Change user password and invalidate all sessions.

        Args:
            user: User object
            current_password: Current password
            new_password: New password

        Raises:
            AuthenticationError: If current password is incorrect
        """
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError(message="Current password is incorrect")

        # Update password
        user.password_hash = hash_password(new_password)
        await self.db.flush()

        # Invalidate all sessions
        await self.session_store.delete_all_user_sessions(str(user.id))

    async def _handle_failed_login(self, user: User) -> None:
        """Handle failed login attempt."""
        user.failed_login_attempts += 1

        # Lock account after threshold
        if user.failed_login_attempts >= settings.account_lockout_threshold:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.account_lockout_duration_minutes
            )

        await self.db.flush()

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if a token is blacklisted."""
        return await self.token_blacklist.is_blacklisted(jti)
