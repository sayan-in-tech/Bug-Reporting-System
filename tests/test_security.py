"""Tests for security features."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Test that security headers are present in responses."""
    response = await client.get("/health")
    assert response.status_code == 200

    # Check security headers
    headers = response.headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert "content-security-policy" in headers


@pytest.mark.asyncio
async def test_cors_preflight(client: AsyncClient):
    """Test CORS preflight request handling."""
    response = await client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Should not fail
    assert response.status_code in [200, 405]


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient):
    """Test that X-Request-ID is returned in responses."""
    response = await client.get("/api/auth/me")
    # Even on error, should have request ID
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    """Test that invalid JWT tokens are rejected."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token_here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_format(client: AsyncClient):
    """Test that malformed tokens are rejected."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_prefix(client: AsyncClient):
    """Test that tokens without Bearer prefix are rejected."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "some_token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_not_returned_in_response(client: AsyncClient):
    """Test that password is never returned in API responses."""
    # Register user
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "securitytest",
            "email": "securitytest@example.com",
            "password": "SecurePassword123!",
        },
    )
    data = response.json()

    # Password should not be in response
    assert "password" not in str(data).lower() or "password" in "SecurePassword123!"
    assert "password_hash" not in str(data).lower()


@pytest.mark.asyncio
async def test_error_response_format(client: AsyncClient):
    """Test that error responses follow consistent format."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
