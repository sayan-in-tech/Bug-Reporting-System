"""Request ID middleware for request tracing."""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request.

    The request ID is added to:
    - request.state.request_id for use in the application
    - X-Request-ID response header for client correlation
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add request ID to request and response."""
        # Check if request ID was provided by client/proxy
        request_id = request.headers.get(self.HEADER_NAME)

        if not request_id:
            # Generate a new request ID
            request_id = str(uuid4())

        # Store in request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers[self.HEADER_NAME] = request_id

        return response
