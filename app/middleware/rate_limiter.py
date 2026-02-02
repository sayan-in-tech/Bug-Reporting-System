"""Rate limiting middleware."""

import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.redis import RateLimiter, get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests.

    Uses Redis-based sliding window rate limiting.
    """

    # Endpoints excluded from rate limiting
    EXCLUDED_PATHS = {
        "/health",
        "/health/ready",
        "/health/live",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Apply rate limiting to the request."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        try:
            redis_client = await get_redis()
            rate_limiter = RateLimiter(redis_client)

            # Check rate limit
            is_allowed, remaining, retry_after = await rate_limiter.is_allowed(
                key=f"api:{client_ip}",
                max_requests=settings.rate_limit_per_minute,
                window_seconds=60,
            )

            if not is_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down.",
                        }
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        except Exception:
            # If Redis is unavailable, allow the request but log the error
            # This prevents rate limiting from blocking the entire API
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get the client IP address from the request."""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"
