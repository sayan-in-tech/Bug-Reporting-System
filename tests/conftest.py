"""Pytest configuration and fixtures."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings, settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.comment import Comment
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.user import User, UserRole
from app.redis import get_redis


# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=0)
    mock.hset = AsyncMock(return_value=1)
    mock.hgetall = AsyncMock(return_value={})
    mock.expire = AsyncMock(return_value=True)
    mock.sadd = AsyncMock(return_value=1)
    mock.srem = AsyncMock(return_value=1)
    mock.smembers = AsyncMock(return_value=set())
    mock.scard = AsyncMock(return_value=0)
    mock.time = AsyncMock(return_value=(1704067200, 0))
    mock.zremrangebyscore = AsyncMock(return_value=0)
    mock.zcard = AsyncMock(return_value=0)
    mock.zadd = AsyncMock(return_value=1)
    mock.zrange = AsyncMock(return_value=[])

    # Create a mock pipeline
    pipeline_mock = MagicMock()
    pipeline_mock.zremrangebyscore = MagicMock(return_value=pipeline_mock)
    pipeline_mock.zcard = MagicMock(return_value=pipeline_mock)
    pipeline_mock.zadd = MagicMock(return_value=pipeline_mock)
    pipeline_mock.expire = MagicMock(return_value=pipeline_mock)
    pipeline_mock.execute = AsyncMock(return_value=[0, 0, 1, True])
    mock.pipeline = MagicMock(return_value=pipeline_mock)

    return mock


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client(db_session: AsyncSession, mock_redis) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


# Fixture factories for creating test data
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("TestPass123!"),
        role=UserRole.DEVELOPER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create a test admin user."""
    user = User(
        id=uuid.uuid4(),
        username="testadmin",
        email="admin@example.com",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_manager(db_session: AsyncSession) -> User:
    """Create a test manager user."""
    user = User(
        id=uuid.uuid4(),
        username="testmanager",
        email="manager@example.com",
        password_hash=hash_password("ManagerPass123!"),
        role=UserRole.MANAGER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, test_manager: User) -> Project:
    """Create a test project."""
    project = Project(
        id=uuid.uuid4(),
        name="Test Project",
        description="A test project description",
        created_by_id=test_manager.id,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_issue(
    db_session: AsyncSession, test_project: Project, test_user: User
) -> Issue:
    """Create a test issue."""
    issue = Issue(
        id=uuid.uuid4(),
        title="Test Issue",
        description="A test issue description",
        status=IssueStatus.OPEN,
        priority=IssuePriority.MEDIUM,
        project_id=test_project.id,
        reporter_id=test_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)
    return issue


@pytest_asyncio.fixture
async def test_comment(
    db_session: AsyncSession, test_issue: Issue, test_user: User
) -> Comment:
    """Create a test comment."""
    comment = Comment(
        id=uuid.uuid4(),
        content="A test comment",
        issue_id=test_issue.id,
        author_id=test_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment


@pytest.fixture
def user_token(test_user: User) -> str:
    """Create a JWT token for the test user."""
    return create_access_token(
        user_id=str(test_user.id),
        role=test_user.role,
        session_id=str(uuid.uuid4()),
    )


@pytest.fixture
def admin_token(test_admin: User) -> str:
    """Create a JWT token for the test admin."""
    return create_access_token(
        user_id=str(test_admin.id),
        role=test_admin.role,
        session_id=str(uuid.uuid4()),
    )


@pytest.fixture
def manager_token(test_manager: User) -> str:
    """Create a JWT token for the test manager."""
    return create_access_token(
        user_id=str(test_manager.id),
        role=test_manager.role,
        session_id=str(uuid.uuid4()),
    )


def auth_header(token: str) -> dict[str, str]:
    """Create an authorization header with the given token."""
    return {"Authorization": f"Bearer {token}"}
