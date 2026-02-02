"""Audit logging middleware."""

import logging
import time
from typing import Any, Optional
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

# Map log level string to logging constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        LOG_LEVELS.get(settings.log_level.upper(), logging.INFO)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Sensitive fields to mask in logs
SENSITIVE_FIELDS = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "credit_card",
    "ssn",
}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware for audit logging of API requests.

    Logs:
    - Request details (method, path, user)
    - Response status and timing
    - Authentication events
    - Sensitive data is masked
    """

    # Paths to exclude from detailed logging
    EXCLUDED_PATHS = {
        "/health",
        "/health/ready",
        "/health/live",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Log request and response details."""
        # Generate request ID
        request_id = str(uuid4())
        request.state.request_id = request_id

        # Skip detailed logging for health checks
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Extract request info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        # Log request
        log_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": self._mask_sensitive(dict(request.query_params)),
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        # Log authentication-related requests with more detail
        if "/auth/" in request.url.path:
            log_context["auth_event_type"] = "auth_request"

        logger.info("request_started", **log_context)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Get user ID if authenticated (stored as string to avoid DetachedInstanceError)
        user_id = getattr(request.state, "user_id", None)

        # Log response
        response_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
        }

        # Determine log level based on status code
        if response.status_code >= 500:
            logger.error("request_completed", **response_context)
        elif response.status_code >= 400:
            logger.warning("request_completed", **response_context)
        else:
            logger.info("request_completed", **response_context)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get the client IP address from the request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    def _mask_sensitive(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive fields in the data."""
        masked = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive(value)
            else:
                masked[key] = value
        return masked


def log_auth_event(
    event: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    success: bool = True,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Log an authentication event.

    Args:
        event: Type of auth event (login, logout, register, password_change)
        user_id: User ID (if known)
        username: Username (masked if failed login)
        success: Whether the operation succeeded
        reason: Reason for failure (if applicable)
        ip_address: Client IP address
        request_id: Request ID for correlation
    """
    context = {
        "event_type": "auth",
        "auth_action": event,
        "success": success,
        "ip_address": ip_address,
        "request_id": request_id,
    }

    if success:
        context["user_id"] = user_id
        context["username"] = username
        logger.info("auth_event", **context)
    else:
        # Don't log full username on failed attempts (prevent enumeration)
        if username:
            context["username_prefix"] = username[:2] + "***"
        context["reason"] = reason
        logger.warning("auth_event", **context)


def log_permission_event(
    action: str,
    resource: str,
    user_id: str,
    granted: bool,
    required_permission: Optional[str] = None,
    user_role: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Log a permission check event.

    Args:
        action: Action attempted (view, create, update, delete)
        resource: Resource type (project, issue, comment)
        user_id: User ID
        granted: Whether permission was granted
        required_permission: Permission that was required
        user_role: User's role
        request_id: Request ID for correlation
    """
    context = {
        "event_type": "permission",
        "action": action,
        "resource": resource,
        "user_id": user_id,
        "granted": granted,
        "required_permission": required_permission,
        "user_role": user_role,
        "request_id": request_id,
    }

    if granted:
        logger.debug("permission_check", **context)
    else:
        logger.warning("permission_denied", **context)


def log_data_modification(
    action: str,
    resource: str,
    resource_id: str,
    user_id: str,
    changes: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Log a data modification event.

    Args:
        action: Action performed (create, update, delete)
        resource: Resource type (project, issue, comment)
        resource_id: ID of the resource
        user_id: User who performed the action
        changes: Dictionary of changes (masked)
        request_id: Request ID for correlation
    """
    context = {
        "event_type": "data_modification",
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "user_id": user_id,
        "request_id": request_id,
    }

    if changes:
        # Mask sensitive fields in changes
        masked_changes = {}
        for key, value in changes.items():
            if key.lower() in SENSITIVE_FIELDS:
                masked_changes[key] = "***MASKED***"
            else:
                masked_changes[key] = value
        context["changes"] = masked_changes

    logger.info("data_modified", **context)
