"""Tests for database models."""

import pytest
from uuid import uuid4
from datetime import datetime

from app.models.user import User, UserRole
from app.models.issue import IssueStatus, IssuePriority


class TestUserModel:
    """Tests for User model."""

    def test_user_role_values(self):
        """Test that user roles have correct values."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.MANAGER.value == "manager"
        assert UserRole.DEVELOPER.value == "developer"

    def test_user_is_admin(self):
        """Test is_admin property."""
        admin = User(
            id=uuid4(),
            username="admin",
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.ADMIN,
        )
        developer = User(
            id=uuid4(),
            username="dev",
            email="dev@example.com",
            password_hash="hash",
            role=UserRole.DEVELOPER,
        )
        assert admin.is_admin is True
        assert developer.is_admin is False

    def test_user_is_manager(self):
        """Test is_manager property."""
        manager = User(
            id=uuid4(),
            username="manager",
            email="manager@example.com",
            password_hash="hash",
            role=UserRole.MANAGER,
        )
        developer = User(
            id=uuid4(),
            username="dev",
            email="dev@example.com",
            password_hash="hash",
            role=UserRole.DEVELOPER,
        )
        assert manager.is_manager is True
        assert developer.is_manager is False


class TestIssueEnums:
    """Tests for Issue enums."""

    def test_issue_status_values(self):
        """Test that issue statuses have correct values."""
        assert IssueStatus.OPEN.value == "open"
        assert IssueStatus.IN_PROGRESS.value == "in_progress"
        assert IssueStatus.RESOLVED.value == "resolved"
        assert IssueStatus.CLOSED.value == "closed"
        assert IssueStatus.REOPENED.value == "reopened"

    def test_issue_priority_values(self):
        """Test that issue priorities have correct values."""
        assert IssuePriority.LOW.value == "low"
        assert IssuePriority.MEDIUM.value == "medium"
        assert IssuePriority.HIGH.value == "high"
        assert IssuePriority.CRITICAL.value == "critical"
