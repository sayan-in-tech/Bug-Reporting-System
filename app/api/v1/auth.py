"""Authentication API endpoints."""

from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, RedisClient
from app.core.exceptions import RateLimitError
from app.database import get_db
from app.redis import RateLimiter, get_redis
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LogoutAllRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth import AuthService

router = APIRouter()


async def check_login_rate_limit(
    request: Request,
    redis_client: Annotated[redis.Redis | None, Depends(get_redis)],
) -> None:
    """Check rate limit for login attempts."""
    # Skip rate limiting if Redis is not available
    if redis_client is None:
        return
    
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = RateLimiter(redis_client)

    is_allowed, remaining, retry_after = await rate_limiter.is_allowed(
        key=f"login:{client_ip}",
        max_requests=5,
        window_seconds=60,
    )

    if not is_allowed:
        raise RateLimitError(
            message="Too many login attempts. Please try again later.",
            retry_after=retry_after,
        )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Register a new user",
    description="Create a new user account and return authentication tokens.",
)
async def register(
    data: RegisterRequest,
    db: DbSession,
    redis_client: RedisClient,
) -> TokenResponse:
    """Register a new user and return tokens."""
    auth_service = AuthService(db, redis_client)

    # Register user
    user = await auth_service.register(data)

    # Authenticate and get tokens
    _, tokens = await auth_service.authenticate(data.username, data.password)

    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to get tokens",
    description="Authenticate with username/email and password to obtain access and refresh tokens.",
    dependencies=[Depends(check_login_rate_limit)],
)
async def login(
    data: LoginRequest,
    db: DbSession,
    redis_client: RedisClient,
) -> TokenResponse:
    """Login and return access and refresh tokens."""
    auth_service = AuthService(db, redis_client)
    _, tokens = await auth_service.authenticate(data.username, data.password)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Use a refresh token to obtain a new access token. The old refresh token is invalidated.",
)
async def refresh(
    data: RefreshRequest,
    db: DbSession,
    redis_client: RedisClient,
) -> TokenResponse:
    """Refresh access token using refresh token."""
    auth_service = AuthService(db, redis_client)
    return await auth_service.refresh_tokens(data.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout current session",
    description="Invalidate the current access token and optionally the refresh token.",
)
async def logout(
    current_user: CurrentUser,
    db: DbSession,
    redis_client: RedisClient,
    authorization: Annotated[str, Header()],
    refresh_token: Annotated[str | None, Body(embed=True)] = None,
) -> MessageResponse:
    """Logout and invalidate tokens."""
    auth_service = AuthService(db, redis_client)

    # Extract access token from Authorization header
    access_token = authorization.replace("Bearer ", "")

    await auth_service.logout(access_token, refresh_token)

    return MessageResponse(message="Successfully logged out")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Logout from all devices",
    description="Invalidate all sessions for the current user. Requires password confirmation.",
)
async def logout_all(
    data: LogoutAllRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis_client: RedisClient,
) -> MessageResponse:
    """Logout from all devices."""
    auth_service = AuthService(db, redis_client)

    # Verify password
    from app.core.security import verify_password
    if not verify_password(data.current_password, current_user.password_hash):
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError(message="Invalid password")

    count = await auth_service.logout_all_devices(str(current_user.id))

    return MessageResponse(message=f"Successfully logged out from {count} device(s)")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current user profile",
    description="Get the profile information of the currently authenticated user.",
)
async def get_me(current_user: CurrentUser) -> CurrentUserResponse:
    """Get current user profile."""
    return CurrentUserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password",
    description="Change the current user's password. This will invalidate all existing sessions.",
)
async def change_password(
    data: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis_client: RedisClient,
) -> MessageResponse:
    """Change user password."""
    auth_service = AuthService(db, redis_client)

    await auth_service.change_password(
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
    )

    return MessageResponse(
        message="Password changed successfully. Please login again with your new password."
    )
