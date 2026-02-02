"""Tests for project endpoints."""

import pytest
from httpx import AsyncClient


async def get_manager_token(client: AsyncClient) -> str:
    """Helper to register a manager user and get token."""
    # Register as admin first (to create a manager)
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "projectmanager",
            "email": "projectmanager@example.com",
            "password": "SecurePassword123!",
        },
    )
    return response.json()["access_token"]


async def get_user_token(client: AsyncClient) -> str:
    """Helper to register a developer user and get token."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "projectdev",
            "email": "projectdev@example.com",
            "password": "SecurePassword123!",
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_list_projects_unauthorized(client: AsyncClient):
    """Test listing projects without authentication."""
    response = await client.get("/api/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_projects_authenticated(client: AsyncClient):
    """Test listing projects with authentication."""
    token = await get_user_token(client)
    response = await client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data


@pytest.mark.asyncio
async def test_create_project_as_developer(client: AsyncClient):
    """Test that developers cannot create projects."""
    token = await get_user_token(client)
    response = await client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Test Project",
            "description": "A test project",
        },
    )
    # Developers should not be able to create projects
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_project_pagination(client: AsyncClient):
    """Test project list pagination parameters."""
    token = await get_user_token(client)
    response = await client.get(
        "/api/projects?page=1&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_project_search(client: AsyncClient):
    """Test project search functionality."""
    token = await get_user_token(client)
    response = await client.get(
        "/api/projects?search=nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
