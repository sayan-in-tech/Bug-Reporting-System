"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_user_invalid_email(client: AsyncClient):
    """Test user registration with invalid email."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "invalid-email",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_user_weak_password(client: AsyncClient):
    """Test user registration with weak password."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "weak",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login."""
    # First register a user
    await client.post(
        "/api/auth/register",
        json={
            "username": "loginuser",
            "email": "loginuser@example.com",
            "password": "SecurePassword123!",
        },
    )

    # Then login
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "loginuser",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials."""
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "nonexistent",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """Test getting current user without authentication."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    """Test getting current user with authentication."""
    # Register and get token
    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": "meuser",
            "email": "meuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = register_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"
    assert data["email"] == "meuser@example.com"


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Test token refresh."""
    # Register and get tokens
    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": "refreshuser",
            "email": "refreshuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    refresh_token = register_response.json()["refresh_token"]

    # Refresh token
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
