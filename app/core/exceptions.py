"""Custom exception classes for the application."""

from typing import Any, Optional

from fastapi import HTTPException, status


class APIException(HTTPException):
    """Base API exception with standardized error format."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[list[dict[str, Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.code = code
        self.error_message = message
        self.details = details

        # Build the error response
        error_body = {
            "error": {
                "code": code,
                "message": message,
            }
        }
        if details:
            error_body["error"]["details"] = details

        super().__init__(
            status_code=status_code,
            detail=error_body,
            headers=headers,
        )


class AuthenticationError(APIException):
    """Authentication failed exception."""

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTHENTICATION_ERROR",
        details: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(APIException):
    """Authorization failed exception."""

    def __init__(
        self,
        message: str = "You don't have permission to perform this action",
        code: str = "AUTHORIZATION_ERROR",
        details: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message,
            details=details,
        )


class NotFoundError(APIException):
    """Resource not found exception."""

    def __init__(
        self,
        resource: str = "Resource",
        message: Optional[str] = None,
        code: str = "NOT_FOUND",
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=message or f"{resource} not found",
        )


class ValidationError(APIException):
    """Validation error exception."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[list[dict[str, Any]]] = None,
        code: str = "VALIDATION_ERROR",
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            message=message,
            details=details,
        )


class ConflictError(APIException):
    """Resource conflict exception."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT_ERROR",
        details: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message,
            details=details,
        )


class RateLimitError(APIException):
    """Rate limit exceeded exception."""

    def __init__(
        self,
        message: str = "Too many requests",
        retry_after: int = 60,
        code: str = "RATE_LIMIT_EXCEEDED",
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=code,
            message=message,
            headers={"Retry-After": str(retry_after)},
        )


class AccountLockedError(APIException):
    """Account locked exception."""

    def __init__(
        self,
        message: str = "Account is temporarily locked due to too many failed login attempts",
        code: str = "ACCOUNT_LOCKED",
        unlock_at: Optional[str] = None,
    ):
        details = None
        if unlock_at:
            details = [{"unlock_at": unlock_at}]

        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            code=code,
            message=message,
            details=details,
        )


class InvalidStatusTransitionError(APIException):
    """Invalid status transition exception."""

    def __init__(
        self,
        current_status: str,
        target_status: str,
        valid_transitions: list[str],
    ):
        message = f"Cannot transition from '{current_status}' to '{target_status}'"
        details = [
            {
                "current_status": current_status,
                "target_status": target_status,
                "valid_transitions": valid_transitions,
            }
        ]
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_STATUS_TRANSITION",
            message=message,
            details=details,
        )


class BusinessRuleError(APIException):
    """Business rule violation exception."""

    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_RULE_VIOLATION",
        details: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=code,
            message=message,
            details=details,
        )
