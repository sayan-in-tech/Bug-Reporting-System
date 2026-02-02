"""Tests for issue endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header


class TestListIssues:
    """Tests for list issues endpoint."""

    @pytest.mark.asyncio
    async def test_list_issues_success(
        self,
        client: AsyncClient,
        test_project: Project,
        test_issue: Issue,
        user_token: str,
    ):
        """Test listing issues in a project."""
        response = await client.get(
            f"/api/projects/{test_project.id}/issues",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_issues_filter_by_status(
        self,
        client: AsyncClient,
        test_project: Project,
        test_issue: Issue,
        user_token: str,
    ):
        """Test listing issues filtered by status."""
        response = await client.get(
            f"/api/projects/{test_project.id}/issues",
            params={"status": "open"},
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.asyncio
    async def test_list_issues_filter_by_priority(
        self,
        client: AsyncClient,
        test_project: Project,
        test_issue: Issue,
        user_token: str,
    ):
        """Test listing issues filtered by priority."""
        response = await client.get(
            f"/api/projects/{test_project.id}/issues",
            params={"priority": "medium"},
            headers=auth_header(user_token),
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_issues_project_not_found(
        self, client: AsyncClient, user_token: str
    ):
        """Test listing issues for non-existent project."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/api/projects/{fake_id}/issues",
            headers=auth_header(user_token),
        )

        assert response.status_code == 404


class TestCreateIssue:
    """Tests for create issue endpoint."""

    @pytest.mark.asyncio
    async def test_create_issue_success(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test creating an issue."""
        response = await client.post(
            f"/api/projects/{test_project.id}/issues",
            headers=auth_header(user_token),
            json={
                "title": "New Issue",
                "description": "Issue description",
                "priority": "high",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Issue"
        assert data["priority"] == "high"
        assert data["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_issue_with_assignee(
        self,
        client: AsyncClient,
        test_project: Project,
        test_user: User,
        user_token: str,
    ):
        """Test creating an issue with an assignee."""
        response = await client.post(
            f"/api/projects/{test_project.id}/issues",
            headers=auth_header(user_token),
            json={
                "title": "Assigned Issue",
                "description": "Issue with assignee",
                "priority": "medium",
                "assignee_id": str(test_user.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["assignee"]["id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_create_issue_empty_title(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test creating an issue with empty title."""
        response = await client.post(
            f"/api/projects/{test_project.id}/issues",
            headers=auth_header(user_token),
            json={
                "title": "",
                "description": "Description",
                "priority": "low",
            },
        )

        assert response.status_code == 422


class TestGetIssue:
    """Tests for get issue endpoint."""

    @pytest.mark.asyncio
    async def test_get_issue_success(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test getting an issue by ID."""
        response = await client.get(
            f"/api/issues/{test_issue.id}",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_issue.id)
        assert data["title"] == test_issue.title

    @pytest.mark.asyncio
    async def test_get_issue_not_found(
        self, client: AsyncClient, user_token: str
    ):
        """Test getting a non-existent issue."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/api/issues/{fake_id}",
            headers=auth_header(user_token),
        )

        assert response.status_code == 404


class TestUpdateIssue:
    """Tests for update issue endpoint."""

    @pytest.mark.asyncio
    async def test_update_issue_title(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test updating issue title."""
        response = await client.patch(
            f"/api/issues/{test_issue.id}",
            headers=auth_header(user_token),
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_issue_status_valid_transition(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test valid status transition (open -> in_progress)."""
        response = await client.patch(
            f"/api/issues/{test_issue.id}",
            headers=auth_header(user_token),
            json={"status": "in_progress"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_issue_status_invalid_transition(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test invalid status transition (open -> resolved)."""
        response = await client.patch(
            f"/api/issues/{test_issue.id}",
            headers=auth_header(user_token),
            json={"status": "resolved"},
        )

        assert response.status_code == 400
        assert "transition" in response.text.lower()

    @pytest.mark.asyncio
    async def test_update_issue_priority(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test updating issue priority."""
        response = await client.patch(
            f"/api/issues/{test_issue.id}",
            headers=auth_header(user_token),
            json={"priority": "critical"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == "critical"


class TestGetIssueTransitions:
    """Tests for get issue transitions endpoint."""

    @pytest.mark.asyncio
    async def test_get_transitions_open_status(
        self, client: AsyncClient, test_issue: Issue, user_token: str
    ):
        """Test getting valid transitions for an open issue."""
        response = await client.get(
            f"/api/issues/{test_issue.id}/transitions",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_status"] == "open"
        assert "in_progress" in data["valid_transitions"]
        assert "closed" in data["valid_transitions"]


class TestIssueStatusStateMachine:
    """Tests for issue status state machine logic."""

    def test_valid_transitions_from_open(self):
        """Test valid transitions from open status."""
        from app.models.issue import VALID_STATUS_TRANSITIONS, IssueStatus

        valid = VALID_STATUS_TRANSITIONS[IssueStatus.OPEN]
        assert IssueStatus.IN_PROGRESS in valid
        assert IssueStatus.CLOSED in valid
        assert IssueStatus.RESOLVED not in valid

    def test_valid_transitions_from_in_progress(self):
        """Test valid transitions from in_progress status."""
        from app.models.issue import VALID_STATUS_TRANSITIONS, IssueStatus

        valid = VALID_STATUS_TRANSITIONS[IssueStatus.IN_PROGRESS]
        assert IssueStatus.RESOLVED in valid
        assert IssueStatus.OPEN in valid

    def test_valid_transitions_from_resolved(self):
        """Test valid transitions from resolved status."""
        from app.models.issue import VALID_STATUS_TRANSITIONS, IssueStatus

        valid = VALID_STATUS_TRANSITIONS[IssueStatus.RESOLVED]
        assert IssueStatus.CLOSED in valid
        assert IssueStatus.REOPENED in valid

    def test_valid_transitions_from_closed(self):
        """Test valid transitions from closed status."""
        from app.models.issue import VALID_STATUS_TRANSITIONS, IssueStatus

        valid = VALID_STATUS_TRANSITIONS[IssueStatus.CLOSED]
        assert IssueStatus.REOPENED in valid
        assert len(valid) == 1

    def test_valid_transitions_from_reopened(self):
        """Test valid transitions from reopened status."""
        from app.models.issue import VALID_STATUS_TRANSITIONS, IssueStatus

        valid = VALID_STATUS_TRANSITIONS[IssueStatus.REOPENED]
        assert IssueStatus.IN_PROGRESS in valid
        assert IssueStatus.RESOLVED in valid
        assert IssueStatus.CLOSED in valid
