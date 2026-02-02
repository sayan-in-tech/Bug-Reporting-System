"""Tests for input validation."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_username_max_length(client: AsyncClient):
    """Test username maximum length validation."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "a" * 51,  # Max is 50
            "email": "test@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_username_min_length(client: AsyncClient):
    """Test username minimum length validation."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "ab",  # Min is 3
            "email": "test@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_email_format_validation(client: AsyncClient):
    """Test email format validation."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "not-an-email",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_password_complexity(client: AsyncClient):
    """Test password complexity requirements."""
    # Too short
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_required_fields(client: AsyncClient):
    """Test that missing required fields return 422."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            # Missing email and password
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_json_body(client: AsyncClient):
    """Test that invalid JSON body returns error."""
    response = await client.post(
        "/api/auth/register",
        content="not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_content_type_validation(client: AsyncClient):
    """Test that wrong content type is handled."""
    response = await client.post(
        "/api/auth/register",
        content="username=test&password=test",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Should either return 415 or 422
    assert response.status_code in [415, 422]


@pytest.mark.asyncio
async def test_uuid_format_validation(client: AsyncClient):
    """Test that invalid UUID format is rejected."""
    # Register to get a token
    reg_response = await client.post(
        "/api/auth/register",
        json={
            "username": "uuidtest",
            "email": "uuidtest@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = reg_response.json()["access_token"]

    # Try to get project with invalid UUID
    response = await client.get(
        "/api/projects/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pagination_limits(client: AsyncClient):
    """Test pagination parameter limits."""
    # Register to get a token
    reg_response = await client.post(
        "/api/auth/register",
        json={
            "username": "paginationtest",
            "email": "paginationtest@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = reg_response.json()["access_token"]

    # Test limit exceeding max
    response = await client.get(
        "/api/projects?limit=1000",  # Max is usually 100
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Test negative page
    response = await client.get(
        "/api/projects?page=-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
