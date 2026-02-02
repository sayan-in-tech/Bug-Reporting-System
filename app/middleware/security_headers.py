"""Security headers middleware."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    # Security headers to add to all responses
    SECURITY_HEADERS = {
        # Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",
        # Prevent clickjacking
        "X-Frame-Options": "DENY",
        # Enable XSS filter (legacy browsers)
        "X-XSS-Protection": "1; mode=block",
        # Control referrer information
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # Prevent caching of sensitive data
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
        # Permissions Policy (formerly Feature-Policy)
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    # Content Security Policy (strict)
    CSP_DIRECTIVES_STRICT = {
        "default-src": "'self'",
        "script-src": "'self'",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https:",
        "font-src": "'self'",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        "base-uri": "'self'",
    }

    # Content Security Policy (relaxed for Swagger UI in debug mode)
    CSP_DIRECTIVES_DEBUG = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
        "img-src": "'self' data: https: https://fastapi.tiangolo.com",
        "font-src": "'self' https://cdn.jsdelivr.net https://fonts.gstatic.com",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        "base-uri": "'self'",
    }

    # Paths that need relaxed CSP for documentation UI
    DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Add security headers
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value

        # Use relaxed CSP for docs pages in debug mode, strict CSP otherwise
        if settings.debug and request.url.path in self.DOCS_PATHS:
            csp_directives = self.CSP_DIRECTIVES_DEBUG
        else:
            csp_directives = self.CSP_DIRECTIVES_STRICT

        csp = "; ".join(f"{k} {v}" for k, v in csp_directives.items())
        response.headers["Content-Security-Policy"] = csp

        # Add HSTS header in production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response
