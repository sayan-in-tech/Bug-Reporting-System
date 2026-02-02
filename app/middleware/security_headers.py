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

    # Content Security Policy
    CSP_DIRECTIVES = {
        "default-src": "'self'",
        "script-src": "'self'",
        "style-src": "'self' 'unsafe-inline'",  # unsafe-inline for Swagger UI
        "img-src": "'self' data: https:",
        "font-src": "'self'",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "form-action": "'self'",
        "base-uri": "'self'",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Add security headers
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value

        # Add Content-Security-Policy
        csp = "; ".join(f"{k} {v}" for k, v in self.CSP_DIRECTIVES.items())
        response.headers["Content-Security-Policy"] = csp

        # Add HSTS header in production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response
