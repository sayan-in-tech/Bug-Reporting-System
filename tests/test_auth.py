"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from tests.conftest import auth_header


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        hashed = hash_password(password)

        assert verify_password("WrongPassword123!", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2


class TestRegister:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "role": "developer",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with weak password."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "weak",
                "role": "developer",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "invalid-email",
                "password": "SecurePass123!",
                "role": "developer",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_username(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate username."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": test_user.username,
                "email": "different@example.com",
                "password": "SecurePass123!",
                "role": "developer",
            },
        )

        assert response.status_code == 422
        assert "username" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate email."""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "differentuser",
                "email": test_user.email,
                "password": "SecurePass123!",
                "role": "developer",
            },
        )

        assert response.status_code == 422
        assert "email" in response.text.lower()


class TestLogin:
    """Tests for login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "TestPass123!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_with_email(self, client: AsyncClient, test_user: User):
        """Test login with email instead of username."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": test_user.email,
                "password": "TestPass123!",
            },
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, client: AsyncClient):
        """Test login with non-existent username."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "TestPass123!",
            },
        )

        assert response.status_code == 401
        assert "invalid credentials" in response.text.lower()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_user: User):
        """Test login with incorrect password."""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": test_user.username,
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401
        assert "invalid credentials" in response.text.lower()


class TestGetMe:
    """Tests for current user profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_success(
        self, client: AsyncClient, test_user: User, user_token: str
    ):
        """Test getting current user profile."""
        response = await client.get(
            "/api/auth/me",
            headers=auth_header(user_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert data["role"] == test_user.role.value

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting profile without authentication."""
        response = await client.get("/api/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Test getting profile with invalid token."""
        response = await client.get(
            "/api/auth/me",
            headers=auth_header("invalid-token"),
        )

        assert response.status_code == 401


class TestRefresh:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401


class TestLogout:
    """Tests for logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(
        self, client: AsyncClient, test_user: User, user_token: str
    ):
        """Test successful logout."""
        response = await client.post(
            "/api/auth/logout",
            headers=auth_header(user_token),
            json={},
        )

        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()


class TestChangePassword:
    """Tests for password change endpoint."""

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(
        self, client: AsyncClient, test_user: User, user_token: str
    ):
        """Test changing password with weak new password."""
        response = await client.post(
            "/api/auth/change-password",
            headers=auth_header(user_token),
            json={
                "current_password": "TestPass123!",
                "new_password": "weak",
            },
        )

        assert response.status_code == 422
