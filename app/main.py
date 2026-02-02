"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app import __version__
from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exceptions import APIException
from app.database import close_db, init_db
from app.middleware.audit_logger import AuditLogMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.redis import close_redis, init_redis
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events handler."""
    # Startup
    await init_db()
    await init_redis()
    yield
    # Shutdown
    await close_db()
    await close_redis()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Production-ready Bug Reporting System API for tracking and managing software bugs.",
    version=__version__,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


# Request size limiting middleware
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""

    MAX_SIZE = 1 * 1024 * 1024  # 1MB

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": f"Request body too large. Maximum size is {self.MAX_SIZE // 1024}KB.",
                    }
                },
            )
        return await call_next(request)


# Add middleware (order matters - first added is outermost)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)


# Exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle custom API exceptions."""
    # Add request ID to error response
    if hasattr(request.state, "request_id"):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            exc.detail["error"]["request_id"] = request.state.request_id

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
        })

    content = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": errors,
        }
    }

    if hasattr(request.state, "request_id"):
        content["error"]["request_id"] = request.state.request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Log the error
    import structlog
    logger = structlog.get_logger()
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        request_id=getattr(request.state, "request_id", None),
    )

    content = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        }
    }

    if hasattr(request.state, "request_id"):
        content["error"]["request_id"] = request.state.request_id

    # Include details in debug mode
    if settings.debug:
        content["error"]["details"] = [
            {"type": type(exc).__name__, "message": str(exc)}
        ]

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )


# Include API routers
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


# Health check endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Basic health check",
)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=__version__,
    )


@app.get(
    "/health/ready",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Readiness probe",
)
async def readiness_check() -> HealthResponse:
    """Readiness probe - checks database and Redis connectivity."""
    from sqlalchemy import text
    from app.database import async_session_maker
    from app.redis import get_redis

    db_status = "healthy"
    redis_status = "healthy"

    # Check database
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        redis_client = await get_redis()
        await redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        database=db_status,
        redis=redis_status,
    )


@app.get(
    "/health/live",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness probe",
)
async def liveness_check() -> HealthResponse:
    """Liveness probe - basic check that the application is running."""
    return HealthResponse(
        status="alive",
        version=__version__,
    )


# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs" if settings.debug else None,
        "health": "/health",
    }
