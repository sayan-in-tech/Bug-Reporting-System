"""Tests for project endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.project import Project
from app.models.user import User
from tests.conftest import auth_header


class TestListProjects:
    """Tests for list projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_success(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test listing projects."""
        response = await client.get(
            "/api/projects",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_projects_unauthorized(self, client: AsyncClient):
        """Test listing projects without authentication."""
        response = await client.get("/api/projects")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_with_search(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test listing projects with search filter."""
        response = await client.get(
            "/api/projects",
            params={"search": "Test"},
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_projects_pagination(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test listing projects with pagination."""
        response = await client.get(
            "/api/projects",
            params={"page": 1, "limit": 10},
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 10


class TestCreateProject:
    """Tests for create project endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client: AsyncClient, manager_token: str
    ):
        """Test creating a project."""
        response = await client.post(
            "/api/projects",
            headers=auth_header(manager_token),
            json={
                "name": "New Project",
                "description": "A new project description",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["description"] == "A new project description"
        assert data["is_archived"] is False

    @pytest.mark.asyncio
    async def test_create_project_unauthorized_role(
        self, client: AsyncClient, user_token: str
    ):
        """Test creating a project as a developer (unauthorized)."""
        response = await client.post(
            "/api/projects",
            headers=auth_header(user_token),
            json={
                "name": "New Project",
                "description": "A new project description",
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_project_duplicate_name(
        self, client: AsyncClient, test_project: Project, manager_token: str
    ):
        """Test creating a project with duplicate name."""
        response = await client.post(
            "/api/projects",
            headers=auth_header(manager_token),
            json={
                "name": test_project.name,
                "description": "Different description",
            },
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_project_empty_name(
        self, client: AsyncClient, manager_token: str
    ):
        """Test creating a project with empty name."""
        response = await client.post(
            "/api/projects",
            headers=auth_header(manager_token),
            json={
                "name": "",
                "description": "A description",
            },
        )

        assert response.status_code == 422


class TestGetProject:
    """Tests for get project endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_success(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test getting a project by ID."""
        response = await client.get(
            f"/api/projects/{test_project.id}",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_project.id)
        assert data["name"] == test_project.name

    @pytest.mark.asyncio
    async def test_get_project_not_found(
        self, client: AsyncClient, user_token: str
    ):
        """Test getting a non-existent project."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/api/projects/{fake_id}",
            headers=auth_header(user_token),
        )

        assert response.status_code == 404


class TestUpdateProject:
    """Tests for update project endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_success(
        self, client: AsyncClient, test_project: Project, manager_token: str
    ):
        """Test updating a project."""
        response = await client.patch(
            f"/api/projects/{test_project.id}",
            headers=auth_header(manager_token),
            json={
                "name": "Updated Project Name",
                "description": "Updated description",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_project_unauthorized(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test updating a project as a developer (unauthorized)."""
        response = await client.patch(
            f"/api/projects/{test_project.id}",
            headers=auth_header(user_token),
            json={
                "name": "Updated Project Name",
            },
        )

        assert response.status_code == 403


class TestArchiveProject:
    """Tests for archive project endpoint."""

    @pytest.mark.asyncio
    async def test_archive_project_success(
        self, client: AsyncClient, test_project: Project, manager_token: str
    ):
        """Test archiving a project."""
        response = await client.delete(
            f"/api/projects/{test_project.id}",
            headers=auth_header(manager_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_archived"] is True

    @pytest.mark.asyncio
    async def test_archive_project_unauthorized(
        self, client: AsyncClient, test_project: Project, user_token: str
    ):
        """Test archiving a project as a developer (unauthorized)."""
        response = await client.delete(
            f"/api/projects/{test_project.id}",
            headers=auth_header(user_token),
        )

        assert response.status_code == 403
