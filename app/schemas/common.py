"""Common Pydantic schemas used across the application."""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorDetail(BaseModel):
    """Error detail for validation errors."""

    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    error: dict[str, Any] = Field(
        ...,
        examples=[
            {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": [{"field": "email", "message": "Invalid email format"}],
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        ],
    )

    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[list[ErrorDetail]] = None,
    ) -> "ErrorResponse":
        """Create an error response."""
        error_dict: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if request_id:
            error_dict["request_id"] = request_id
        if details:
            error_dict["details"] = [d.model_dump() for d in details]
        return cls(error=error_dict)


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, limit: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + limit - 1) // limit if limit > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: Optional[str] = None
    redis: Optional[str] = None
