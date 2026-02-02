"""API dependencies for authentication and authorization."""

import uuid
from typing import Annotated, Optional

import redis.asyncio as redis
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.permissions import Permission, has_permission
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole
from app.redis import get_redis, TokenBlacklist

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> User:
    """
    Get the current authenticated user from the JWT token.

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials
        db: Database session
        redis_client: Redis client

    Returns:
        Authenticated user

    Raises:
        AuthenticationError: If authentication fails
    """
    if not credentials:
        raise AuthenticationError(message="Authentication required")

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise AuthenticationError(message="Invalid or expired token")

    # Validate token type
    if payload.get("type") != "access":
        raise AuthenticationError(message="Invalid token type")

    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti:
        blacklist = TokenBlacklist(redis_client)
        if await blacklist.is_blacklisted(jti):
            raise AuthenticationError(message="Token has been revoked")

    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(message="Invalid token payload")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise AuthenticationError(message="Invalid user ID in token")

    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError(message="User not found")

    if not user.is_active:
        raise AuthenticationError(message="Account is deactivated")

    # Store user ID in request state for logging (avoid DetachedInstanceError)
    request.state.user_id = str(user.id)

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current active user.

    Args:
        current_user: Current authenticated user

    Returns:
        Active user

    Raises:
        AuthenticationError: If user is not active
    """
    if not current_user.is_active:
        raise AuthenticationError(message="Account is deactivated")
    return current_user


async def get_optional_user(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.

    This is useful for endpoints that have different behavior for
    authenticated vs anonymous users.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(request, credentials, db, redis_client)
    except AuthenticationError:
        return None


def require_role(*roles: UserRole):
    """
    Dependency to require specific roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_only(...):
            ...
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise AuthorizationError(
                message="You don't have permission to access this resource",
                details=[
                    {
                        "required_roles": [r.value for r in roles],
                        "user_role": current_user.role.value,
                    }
                ],
            )
        return current_user

    return role_checker


def require_permission(*permissions: Permission, require_all: bool = False):
    """
    Dependency to require specific permissions.

    Usage:
        @router.post("/projects", dependencies=[Depends(require_permission(Permission.CREATE_PROJECT))])
        async def create_project(...):
            ...
    """

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if require_all:
            has_perms = all(has_permission(current_user, p) for p in permissions)
        else:
            has_perms = any(has_permission(current_user, p) for p in permissions)

        if not has_perms:
            raise AuthorizationError(
                message="You don't have permission to perform this action",
                details=[
                    {
                        "required_permissions": [p.value for p in permissions],
                        "user_role": current_user.role.value,
                    }
                ],
            )
        return current_user

    return permission_checker


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Optional[redis.Redis], Depends(get_redis)]
