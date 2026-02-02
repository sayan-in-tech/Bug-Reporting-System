"""Tests for utility functions."""

import pytest

from app.utils.markdown_sanitizer import sanitize_markdown, strip_all_html, escape_html
from app.utils.validators import (
    validate_path_traversal,
    validate_uuid,
    sanitize_filename,
    is_valid_email,
    is_safe_url,
)


class TestMarkdownSanitizer:
    """Tests for markdown sanitization."""

    def test_sanitize_basic_html(self):
        """Test that basic safe HTML is preserved."""
        content = "<p>Hello <strong>World</strong></p>"
        result = sanitize_markdown(content)
        assert "<p>" in result
        assert "<strong>" in result

    def test_sanitize_script_tags(self):
        """Test that script tags are removed."""
        content = "<script>alert('xss')</script>Hello"
        result = sanitize_markdown(content)
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_event_handlers(self):
        """Test that event handlers are removed."""
        content = "<div onclick='alert(1)'>Click me</div>"
        result = sanitize_markdown(content)
        assert "onclick" not in result

    def test_sanitize_javascript_urls(self):
        """Test that javascript: URLs are removed."""
        content = "<a href='javascript:alert(1)'>Link</a>"
        result = sanitize_markdown(content)
        assert "javascript:" not in result

    def test_sanitize_empty_content(self):
        """Test sanitizing empty content."""
        assert sanitize_markdown("") == ""
        assert sanitize_markdown(None) is None

    def test_strip_all_html(self):
        """Test stripping all HTML tags."""
        content = "<p>Hello <strong>World</strong></p>"
        result = strip_all_html(content)
        assert "<" not in result
        assert ">" not in result
        assert "Hello" in result
        assert "World" in result

    def test_escape_html(self):
        """Test HTML escaping."""
        content = "<script>alert('test')</script>"
        result = escape_html(content)
        assert "&lt;" in result
        assert "&gt;" in result
        assert "<script>" not in result


class TestValidators:
    """Tests for validation utilities."""

    def test_validate_uuid_valid(self):
        """Test UUID validation with valid UUID."""
        result = validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert result is not None

    def test_validate_uuid_invalid(self):
        """Test UUID validation with invalid string."""
        result = validate_uuid("invalid-uuid")
        assert result is None

    def test_validate_uuid_empty(self):
        """Test UUID validation with empty string."""
        result = validate_uuid("")
        assert result is None

    def test_path_traversal_safe(self):
        """Test path traversal detection with safe path."""
        assert validate_path_traversal("/safe/path/file.txt") is True
        assert validate_path_traversal("filename.txt") is True

    def test_path_traversal_unsafe(self):
        """Test path traversal detection with unsafe paths."""
        assert validate_path_traversal("../etc/passwd") is False
        assert validate_path_traversal("..\\windows\\system32") is False
        assert validate_path_traversal("path/../../../etc/passwd") is False

    def test_path_traversal_null_byte(self):
        """Test path traversal with null byte injection."""
        assert validate_path_traversal("file.txt\x00.jpg") is False

    def test_sanitize_filename_safe(self):
        """Test filename sanitization with safe filename."""
        result = sanitize_filename("document.pdf")
        assert result == "document.pdf"

    def test_sanitize_filename_path_separators(self):
        """Test filename sanitization removes path separators."""
        result = sanitize_filename("../path/file.txt")
        assert "/" not in result
        assert ".." not in result

    def test_sanitize_filename_special_chars(self):
        """Test filename sanitization removes special characters."""
        result = sanitize_filename("file<>:*.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "*" not in result

    def test_sanitize_filename_empty(self):
        """Test filename sanitization with empty filename."""
        result = sanitize_filename("")
        assert result == ""

    def test_is_valid_email_valid(self):
        """Test email validation with valid emails."""
        assert is_valid_email("user@example.com") is True
        assert is_valid_email("user.name@domain.co.uk") is True

    def test_is_valid_email_invalid(self):
        """Test email validation with invalid emails."""
        assert is_valid_email("invalid") is False
        assert is_valid_email("@example.com") is False
        assert is_valid_email("user@") is False
        assert is_valid_email("") is False

    def test_is_safe_url_relative(self):
        """Test URL safety check with relative URLs."""
        assert is_safe_url("/path/to/page") is True
        assert is_safe_url("/") is True

    def test_is_safe_url_absolute(self):
        """Test URL safety check with absolute URLs."""
        assert is_safe_url("https://example.com") is True
        assert is_safe_url("http://example.com") is True

    def test_is_safe_url_javascript(self):
        """Test URL safety check with javascript URLs."""
        assert is_safe_url("javascript:alert(1)") is False

    def test_is_safe_url_data(self):
        """Test URL safety check with data URLs."""
        assert is_safe_url("data:text/html,<script>") is False


class TestPermissions:
    """Tests for permission system."""

    def test_role_permissions_developer(self):
        """Test developer role permissions."""
        from app.core.permissions import ROLE_PERMISSIONS, Permission
        from app.models.user import UserRole

        perms = ROLE_PERMISSIONS[UserRole.DEVELOPER]
        assert Permission.VIEW_PROJECTS in perms
        assert Permission.VIEW_ISSUES in perms
        assert Permission.CREATE_ISSUE in perms
        assert Permission.ADD_COMMENT in perms
        assert Permission.CREATE_PROJECT not in perms

    def test_role_permissions_manager(self):
        """Test manager role permissions."""
        from app.core.permissions import ROLE_PERMISSIONS, Permission
        from app.models.user import UserRole

        perms = ROLE_PERMISSIONS[UserRole.MANAGER]
        assert Permission.CREATE_PROJECT in perms
        assert Permission.EDIT_PROJECT in perms
        assert Permission.CHANGE_ASSIGNEE in perms

    def test_role_permissions_admin(self):
        """Test admin role has all permissions."""
        from app.core.permissions import ROLE_PERMISSIONS, Permission
        from app.models.user import UserRole

        admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
        all_perms = set(Permission)
        assert admin_perms == all_perms


class TestModels:
    """Tests for model methods and properties."""

    def test_issue_can_transition_to(self):
        """Test issue status transition checking."""
        from app.models.issue import Issue, IssueStatus

        issue = Issue()
        issue.status = IssueStatus.OPEN

        assert issue.can_transition_to(IssueStatus.IN_PROGRESS) is True
        assert issue.can_transition_to(IssueStatus.CLOSED) is True
        assert issue.can_transition_to(IssueStatus.RESOLVED) is False

    def test_issue_get_valid_transitions(self):
        """Test getting valid transitions for issue."""
        from app.models.issue import Issue, IssueStatus

        issue = Issue()
        issue.status = IssueStatus.OPEN

        valid = issue.get_valid_transitions()
        assert IssueStatus.IN_PROGRESS in valid
        assert IssueStatus.CLOSED in valid

    def test_issue_is_critical(self):
        """Test issue is_critical property."""
        from app.models.issue import Issue, IssuePriority

        issue = Issue()
        issue.priority = IssuePriority.CRITICAL
        assert issue.is_critical is True

        issue.priority = IssuePriority.HIGH
        assert issue.is_critical is False

    def test_user_is_admin(self):
        """Test user is_admin property."""
        from app.models.user import User, UserRole

        user = User()
        user.role = UserRole.ADMIN
        assert user.is_admin is True

        user.role = UserRole.DEVELOPER
        assert user.is_admin is False

    def test_user_is_manager(self):
        """Test user is_manager property."""
        from app.models.user import User, UserRole

        user = User()
        user.role = UserRole.MANAGER
        assert user.is_manager is True

        user.role = UserRole.ADMIN
        assert user.is_manager is True

        user.role = UserRole.DEVELOPER
        assert user.is_manager is False
