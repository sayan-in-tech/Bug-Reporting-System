"""Pytest configuration and fixtures."""

import os
from unittest.mock import AsyncMock, MagicMock

# Set test environment variables BEFORE any app imports
# Don't set JWT_PRIVATE_KEY - let it fall back to HS256 with SECRET_KEY
os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-not-for-production"
# Use in-memory SQLite for tests - fastest option
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
# Disable Redis for tests
os.environ["REDIS_URL"] = ""

# Now safe to import
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Now import app modules (after env vars are set)
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.comment import Comment
from app.core.security import hash_password, create_access_token
from app.main import app


def auth_header(token: str) -> dict:
    """Create authorization header with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis for all tests."""
    mock_redis_client = MagicMock()
    mock_redis_client.get = AsyncMock(return_value=None)
    mock_redis_client.set = AsyncMock(return_value=True)
    mock_redis_client.setex = AsyncMock(return_value=True)
    mock_redis_client.delete = AsyncMock(return_value=True)
    mock_redis_client.exists = AsyncMock(return_value=0)
    mock_redis_client.incr = AsyncMock(return_value=1)
    mock_redis_client.expire = AsyncMock(return_value=True)
    mock_redis_client.ttl = AsyncMock(return_value=-2)
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.close = AsyncMock()
    
    # Mock the get_redis function
    async def mock_get_redis():
        return mock_redis_client
    
    try:
        from app.core import redis as redis_module
        monkeypatch.setattr(redis_module, "get_redis", mock_get_redis)
        monkeypatch.setattr(redis_module, "redis_client", mock_redis_client)
    except (ImportError, AttributeError):
        pass  # Redis module might not exist or have different structure
    
    return mock_redis_client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory database for each test."""
    # Create new engine for each test (in-memory DB is isolated)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
async def user_token(test_user: User) -> str:
    """Create a JWT token for the test user."""
    return create_access_token(
        user_id=str(test_user.id),
        role=test_user.role,
        session_id=str(uuid4()),
    )


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    """Create a JWT token for the admin user."""
    return create_access_token(
        user_id=str(admin_user.id),
        role=admin_user.role,
        session_id=str(uuid4()),
    )


@pytest_asyncio.fixture
async def manager_token(manager_user: User) -> str:
    """Create a JWT token for the manager user."""
    return create_access_token(
        user_id=str(manager_user.id),
        role=manager_user.role,
        session_id=str(uuid4()),
    )


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, admin_user: User) -> Project:
    """Create a test project."""
    project = Project(
        id=uuid4(),
        name="Test Project",
        description="A test project for testing purposes",
        created_by_id=admin_user.id,
        is_archived=False,
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
        id=uuid4(),
        title="Test Issue",
        description="A test issue for testing purposes",
        status=IssueStatus.OPEN,
        priority=IssuePriority.MEDIUM,
        project_id=test_project.id,
        reporter_id=test_user.id,
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
        id=uuid4(),
        content="Test comment content",
        issue_id=test_issue.id,
        author_id=test_user.id,
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment
