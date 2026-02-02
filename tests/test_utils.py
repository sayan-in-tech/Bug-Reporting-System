"""Tests for utility functions."""

import pytest
from uuid import uuid4

from app.utils.validators import (
    validate_uuid,
    validate_path_traversal,
    validate_content_type,
    validate_query_params,
    sanitize_filename,
    is_valid_email,
    is_safe_url,
)
from app.utils.markdown_sanitizer import sanitize_markdown


class TestUuidValidator:
    """Tests for UUID validation."""

    def test_valid_uuid(self):
        """Test that valid UUIDs pass validation."""
        valid_uuid = str(uuid4())
        result = validate_uuid(valid_uuid)
        assert result is not None

    def test_invalid_uuid(self):
        """Test that invalid UUIDs fail validation."""
        assert validate_uuid("not-a-uuid") is None
        assert validate_uuid("12345") is None
        assert validate_uuid("") is None


class TestPathTraversalValidator:
    """Tests for path traversal detection."""

    def test_safe_path(self):
        """Test that safe paths pass validation."""
        assert validate_path_traversal("normal/path/file.txt") is True
        assert validate_path_traversal("file.txt") is True

    def test_path_traversal_detected(self):
        """Test that path traversal is detected."""
        assert validate_path_traversal("../etc/passwd") is False
        assert validate_path_traversal("..\\windows\\system32") is False
        assert validate_path_traversal("path/../../file") is False


class TestContentTypeValidator:
    """Tests for content type validation."""

    def test_valid_content_type(self):
        """Test valid content types."""
        allowed = ["application/json", "text/plain"]
        assert validate_content_type("application/json", allowed) is True
        assert validate_content_type("application/json; charset=utf-8", allowed) is True

    def test_invalid_content_type(self):
        """Test invalid content types."""
        allowed = ["application/json"]
        assert validate_content_type("text/html", allowed) is False
        assert validate_content_type(None, allowed) is False


class TestQueryParamsValidator:
    """Tests for query params filtering."""

    def test_filter_params(self):
        """Test that only allowed params are kept."""
        params = {"page": 1, "limit": 10, "evil": "value"}
        allowed = ["page", "limit"]
        result = validate_query_params(params, allowed)
        assert result == {"page": 1, "limit": 10}
        assert "evil" not in result


class TestFilenameSanitizer:
    """Tests for filename sanitization."""

    def test_safe_filename(self):
        """Test that safe filenames are preserved."""
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("my_file-1.txt") == "my_file-1.txt"

    def test_dangerous_filename(self):
        """Test that dangerous filenames are sanitized."""
        assert "/" not in sanitize_filename("../etc/passwd")
        assert "\\" not in sanitize_filename("..\\windows\\system32")

    def test_empty_filename(self):
        """Test empty filename handling."""
        assert sanitize_filename("") == ""
        assert sanitize_filename("..") == "unnamed"


class TestEmailValidator:
    """Tests for email validation."""

    def test_valid_email(self):
        """Test valid email addresses."""
        assert is_valid_email("user@example.com") is True
        assert is_valid_email("test.user@domain.org") is True

    def test_invalid_email(self):
        """Test invalid email addresses."""
        assert is_valid_email("not-an-email") is False
        assert is_valid_email("@example.com") is False
        assert is_valid_email("user@") is False
        assert is_valid_email("") is False


class TestUrlValidator:
    """Tests for URL safety validation."""

    def test_safe_url(self):
        """Test safe URLs."""
        assert is_safe_url("https://example.com") is True
        assert is_safe_url("/relative/path") is True

    def test_unsafe_url(self):
        """Test unsafe URLs."""
        assert is_safe_url("javascript:alert(1)") is False
        assert is_safe_url("") is False


class TestMarkdownSanitizer:
    """Tests for markdown sanitization."""

    def test_basic_markdown(self):
        """Test that basic markdown is preserved."""
        text = "# Heading\n\nSome **bold** text."
        result = sanitize_markdown(text)
        assert "Heading" in result
        assert "bold" in result

    def test_xss_script_removed(self):
        """Test that script tags are removed (content becomes harmless text)."""
        text = "<script>alert('xss')</script>Hello"
        result = sanitize_markdown(text)
        # Script tags should be stripped (preventing execution)
        assert "<script>" not in result
        assert "</script>" not in result
        # The text content remains but is harmless without the script tags
        assert "Hello" in result

    def test_dangerous_attributes_removed(self):
        """Test that dangerous attributes are removed."""
        text = '<a href="javascript:alert(1)">Link</a>'
        result = sanitize_markdown(text)
        assert "javascript:" not in result

    def test_safe_links_preserved(self):
        """Test that safe links are preserved."""
        text = '<a href="https://example.com">Link</a>'
        result = sanitize_markdown(text)
        assert "https://example.com" in result

    def test_code_blocks_preserved(self):
        """Test that code blocks are preserved."""
        text = "```python\nprint('hello')\n```"
        result = sanitize_markdown(text)
        assert "print" in result
