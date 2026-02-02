"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.models.user import User, UserRole
from app.core.security import hash_password

# Generate test JWT keys if not present
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MaXX9eKux8nmwP5Y
Nhjd4EG3q4Z8r3YmC4qPdFl0j5IwRAu8HxRmI2FBJZPiT6r/eOqR9B6oCu1j4ixJ
v5E7d6dC7c+M6K9odNCLf8wC3Z2Wnj9EwkNYqKQKKrJm+0VdC9kYTVmLJBGmGsnQ
QJlqHB5pdMFuT8EHEGzBgO3SSVIrA4Q6M3SYvNX4qwVhH0+aPWOrfP5W7eNL2P2r
k2v7mMGO8foDqRm0f2Ey2Xo10ck0cD3cEqZmI2kA5v3RMPPdnXsXBCAX7GsAnYaC
TYZ8bEjEbOZmoTVsFmFi4RHw0aMPPvH9e7mCzwIDAQABAoIBAC5RgZ+hBx7xHnFZ
nQmY9IyGvQWNTl1lBvzP0NJlqHGFotPlyMDMVYzy182lIU7KfzxpBhBvzF4o6cHv
cXQb3M5VJ5t+ZzpFbLhaBjCnW/gi8f3p/7cMS0Kn1PNTA3CX2c5iFDJeG5CVNcNC
Euo/W0qL0DAXX4G13N+PQx4/zrHBj9T5x1QxsXsOEh7aR2wdxFyupD3FLi0ZMNBA
bGCCzvoADQ8xL7WpWKaXYKG8G5h0x1YRZeTPrvmTQx0vLBCS+mZs1GK1c6ct9QBT
qhc7wHJ4CpSXLNPyDQrBcZ9NeYg8GGi+L9E9f+HmMYIy7frGYmrVDB9fq8M9JFYE
dYaHqWECgYEA7mI9sK0I6Kf3Yw7YT3Fm9l0R15H6kL18iwG0bLC9z4D0ez0C/5TZ
j9g0kvUKUg4VK5hJ3N3FpUOyPLHB56pYQ0LM6Q0bWa1O0ymPe2e3bQ3y4q0IL0hj
7W0faP0fjhy4VU35yPH9gQyb8mVKFf0f6pCCmL9xD6Be+PDn6CpPyHkCgYEA4SOY
6uzJYJ7A0fRz3Tqie/YdnpCkwz8l5npnJKNvFzVE5jJUbvBDo6L+l7bxPQs4LBTj
x9yLX9BqCl2fjLgCBq4JwIRb7PhdnLV5WNHBQy9p+fPD0vO9pPyU8Vcf8jPNL6Wu
PMBhkhc4bvawCmS2d1UhJIr6dGtONM1yMm79rW8CgYEAwsxlJL09HrLDnxP3qpMT
q4H/9AQ3nsjJB0GLDJfIy7nKcTxQhzx8bmc7LGCR6sP+FvDxDE8qRmT/k3DRQwSD
tZ3Gj0KMLZ7xPObxsULmrQ+gLyP5Wo58J3aMBl1h0D1IhT7QGh4f0RrsC+3h4qEZ
1YLH5bwPofxeUY4L0O3mHYECgYAy0hcGfIRzeeE5u+EfxiM5xD6R7kE0M7QKVHGU
mI7Lwfs8dYn3/1sKhKJvMGFxb0Yz/FfPJqW9cX6DaWb5fKRnoqPnqF0LM5pMwGZn
mbv+M5II4rlCP1TneLFb1n7sHHPuOQh7eoMGNa8cfXVqCsYOso5WEqUHBwpCXDBE
8S2k6wKBgQCEPLB9QoIfLHTJBZSCYqymH6nh2GCta5s0yr89ns6gk6HDP1G1x0ND
RzLO8jDdgC1q9pPXv9H7Jhz5B0Lx1S0nQuxT7MRGZ5m2O7HJHPbqLbLnNoBMu+xn
L3EtLKxZLmMF5GPKkjT3qT3QJ5VhKz4D3tvYHdty6Hxq4xF0vJxdXw==
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/ygWy
F8PbnGy0AHB7MaXX9eKux8nmwP5YNhjd4EG3q4Z8r3YmC4qPdFl0j5IwRAu8HxRm
I2FBJZPiT6r/eOqR9B6oCu1j4ixJv5E7d6dC7c+M6K9odNCLf8wC3Z2Wnj9EwkNY
qKQKKrJm+0VdC9kYTVmLJBGmGsnQQJlqHB5pdMFuT8EHEGzBgO3SSVIrA4Q6M3SY
vNX4qwVhH0+aPWOrfP5W7eNL2P2rk2v7mMGO8foDqRm0f2Ey2Xo10ck0cD3cEqZm
I2kA5v3RMPPdnXsXBCAX7GsAnYaCTYZ8bEjEbOZmoTVsFmFi4RHw0aMPPvH9e7mC
zwIDAQAB
-----END PUBLIC KEY-----"""

# Set test environment variables
os.environ.setdefault("JWT_PRIVATE_KEY", TEST_PRIVATE_KEY)
os.environ.setdefault("JWT_PUBLIC_KEY", TEST_PUBLIC_KEY)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DEBUG", "true")

# Import app after setting env vars
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine."""
    # Use PostgreSQL from environment or default test database
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/bug_tracker_test",
    )

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with the test database."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=UserRole.DEVELOPER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        id=uuid4(),
        username="adminuser",
        email="admin@example.com",
        password_hash=hash_password("AdminPassword123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def manager_user(db_session: AsyncSession) -> User:
    """Create a manager user."""
    user = User(
        id=uuid4(),
        username="manageruser",
        email="manager@example.com",
        password_hash=hash_password("ManagerPassword123!"),
        role=UserRole.MANAGER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
