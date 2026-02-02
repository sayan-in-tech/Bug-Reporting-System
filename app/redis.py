"""Redis connection and utilities."""

from typing import Optional

import redis.asyncio as redis

from app.config import settings

# Global Redis connection pool
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis() -> redis.Redis:
    """Initialize Redis connection pool."""
    global redis_pool, redis_client

    redis_pool = redis.ConnectionPool.from_url(
        settings.redis_url,
        password=settings.redis_password if settings.redis_password else None,
        decode_responses=True,
        max_connections=50,
    )
    redis_client = redis.Redis(connection_pool=redis_pool)

    # Test connection
    await redis_client.ping()

    return redis_client


async def get_redis() -> redis.Redis:
    """Get Redis client dependency."""
    if redis_client is None:
        return await init_redis()
    return redis_client


async def close_redis() -> None:
    """Close Redis connection pool."""
    global redis_pool, redis_client

    if redis_client:
        await redis_client.close()
    if redis_pool:
        await redis_pool.disconnect()

    redis_client = None
    redis_pool = None


class TokenBlacklist:
    """Redis-based token blacklist for invalidated JWTs."""

    PREFIX = "token_blacklist:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def add(self, jti: str, expires_in: int) -> None:
        """Add a token to the blacklist."""
        key = f"{self.PREFIX}{jti}"
        await self.redis.setex(key, expires_in, "1")

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if a token is blacklisted."""
        key = f"{self.PREFIX}{jti}"
        return await self.redis.exists(key) > 0

    async def remove(self, jti: str) -> None:
        """Remove a token from the blacklist."""
        key = f"{self.PREFIX}{jti}"
        await self.redis.delete(key)


class SessionStore:
    """Redis-based session store for refresh tokens."""

    PREFIX = "session:"
    USER_SESSIONS_PREFIX = "user_sessions:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def create(
        self, session_id: str, user_id: str, refresh_token: str, expires_in: int
    ) -> None:
        """Create a new session."""
        session_key = f"{self.PREFIX}{session_id}"
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"

        # Store session data
        await self.redis.hset(
            session_key,
            mapping={
                "user_id": user_id,
                "refresh_token": refresh_token,
            },
        )
        await self.redis.expire(session_key, expires_in)

        # Add to user's session list
        await self.redis.sadd(user_sessions_key, session_id)

    async def get(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        session_key = f"{self.PREFIX}{session_id}"
        data = await self.redis.hgetall(session_key)
        return data if data else None

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        session_key = f"{self.PREFIX}{session_id}"
        session_data = await self.redis.hgetall(session_key)

        if session_data and "user_id" in session_data:
            user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{session_data['user_id']}"
            await self.redis.srem(user_sessions_key, session_id)

        await self.redis.delete(session_key)

    async def delete_all_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user (logout all devices)."""
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        session_ids = await self.redis.smembers(user_sessions_key)

        count = 0
        for session_id in session_ids:
            session_key = f"{self.PREFIX}{session_id}"
            await self.redis.delete(session_key)
            count += 1

        await self.redis.delete(user_sessions_key)
        return count

    async def get_user_session_count(self, user_id: str) -> int:
        """Get the number of active sessions for a user."""
        user_sessions_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
        return await self.redis.scard(user_sessions_key)


class RateLimiter:
    """Redis-based sliding window rate limiter."""

    PREFIX = "rate_limit:"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def is_allowed(
        self, key: str, max_requests: int, window_seconds: int = 60
    ) -> tuple[bool, int, int]:
        """
        Check if a request is allowed under rate limit.

        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        rate_key = f"{self.PREFIX}{key}"
        current_time = await self.redis.time()
        current_timestamp = current_time[0]
        window_start = current_timestamp - window_seconds

        # Use a pipeline for atomic operations
        pipe = self.redis.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(rate_key, 0, window_start)
        # Count current entries
        pipe.zcard(rate_key)
        # Add current request
        pipe.zadd(rate_key, {str(current_timestamp): current_timestamp})
        # Set expiry on the key
        pipe.expire(rate_key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= max_requests:
            # Get the oldest entry to calculate retry-after
            oldest = await self.redis.zrange(rate_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1]) + window_seconds - current_timestamp
                return False, 0, max(retry_after, 1)
            return False, 0, window_seconds

        remaining = max_requests - current_count - 1
        return True, remaining, 0

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        rate_key = f"{self.PREFIX}{key}"
        await self.redis.delete(rate_key)
