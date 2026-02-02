"""Input validation utilities."""

import re
import uuid
from typing import Optional


def validate_uuid(value: str) -> Optional[uuid.UUID]:
    """
    Validate and parse a UUID string.

    Args:
        value: String to validate as UUID

    Returns:
        UUID object if valid, None otherwise
    """
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def validate_path_traversal(path: str) -> bool:
    """
    Check if a path contains potential path traversal patterns.

    Args:
        path: Path string to validate

    Returns:
        True if path is safe, False if it contains traversal patterns
    """
    if not path:
        return True

    # Check for common path traversal patterns
    dangerous_patterns = [
        "..",
        "..\\",
        "../",
        "%2e%2e",  # URL encoded ..
        "%252e%252e",  # Double URL encoded ..
        "....//",
        "..../\\",
        ".../",
        "...\\",
    ]

    path_lower = path.lower()
    for pattern in dangerous_patterns:
        if pattern in path_lower:
            return False

    # Check for null bytes
    if "\x00" in path:
        return False

    return True


def validate_content_type(content_type: Optional[str], allowed_types: list[str]) -> bool:
    """
    Validate Content-Type header against allowed types.

    Args:
        content_type: Content-Type header value
        allowed_types: List of allowed content types

    Returns:
        True if content type is allowed, False otherwise
    """
    if not content_type:
        return False

    # Parse content type (ignore parameters like charset)
    main_type = content_type.split(";")[0].strip().lower()

    return main_type in [t.lower() for t in allowed_types]


def validate_query_params(params: dict, allowed_params: list[str]) -> dict:
    """
    Filter query parameters to only include allowed ones.

    Args:
        params: Dictionary of query parameters
        allowed_params: List of allowed parameter names

    Returns:
        Filtered dictionary containing only allowed parameters
    """
    return {k: v for k, v in params.items() if k in allowed_params}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for use
    """
    if not filename:
        return ""

    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Only allow safe characters
    filename = re.sub(r"[^\w\-_\. ]", "", filename)

    # Limit length
    filename = filename[:255]

    # Prevent empty or dot-only filenames
    if not filename or filename in (".", ".."):
        return "unnamed"

    return filename


def is_valid_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise
    """
    if not email:
        return False

    # Basic email pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_safe_url(url: str, allowed_hosts: Optional[list[str]] = None) -> bool:
    """
    Check if a URL is safe for redirection.

    Args:
        url: URL to validate
        allowed_hosts: List of allowed host names (optional)

    Returns:
        True if URL is safe, False otherwise
    """
    if not url:
        return False

    # Only allow http and https protocols
    if not url.startswith(("http://", "https://", "/")):
        return False

    # If relative URL, it's safe
    if url.startswith("/") and not url.startswith("//"):
        return True

    # If allowed_hosts specified, check against them
    if allowed_hosts:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc in allowed_hosts

    return True
