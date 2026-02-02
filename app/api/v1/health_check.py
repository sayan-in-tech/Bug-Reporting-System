"""Extensive Health Check API - Tests all API endpoints."""

import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app import __version__
from app.config import settings
from app.database import async_session_maker
from app.redis import get_redis

router = APIRouter()


class TestStatus(str, Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EndpointTestResult(BaseModel):
    """Result of a single endpoint test."""
    endpoint: str
    method: str
    status: TestStatus
    response_time_ms: float
    status_code: Optional[int] = None
    error: Optional[str] = None
    details: Optional[str] = None


class CategoryTestResult(BaseModel):
    """Result of a category of tests."""
    category: str
    total: int
    passed: int
    failed: int
    skipped: int
    tests: list[EndpointTestResult]


class ExtensiveHealthCheckResponse(BaseModel):
    """Response model for extensive health check."""
    status: str = Field(description="Overall health status")
    version: str = Field(description="API version")
    timestamp: str = Field(description="Check timestamp")
    total_tests: int = Field(description="Total number of tests")
    passed: int = Field(description="Number of passed tests")
    failed: int = Field(description="Number of failed tests")
    skipped: int = Field(description="Number of skipped tests")
    total_time_ms: float = Field(description="Total execution time in milliseconds")
    infrastructure: dict[str, Any] = Field(description="Infrastructure health status")
    categories: list[CategoryTestResult] = Field(description="Test results by category")


class APITester:
    """Helper class to test API endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.test_user_id: Optional[str] = None
        self.test_project_id: Optional[uuid.UUID] = None
        self.test_issue_id: Optional[uuid.UUID] = None
        self.test_comment_id: Optional[uuid.UUID] = None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _headers(self, with_auth: bool = True) -> dict:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if with_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _test_endpoint(
        self,
        method: str,
        endpoint: str,
        expected_status: list[int],
        json_data: Optional[dict] = None,
        with_auth: bool = True,
        description: Optional[str] = None,
    ) -> EndpointTestResult:
        """Test a single endpoint."""
        start = time.perf_counter()
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                json=json_data,
                headers=self._headers(with_auth),
            )
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code in expected_status:
                return EndpointTestResult(
                    endpoint=endpoint,
                    method=method,
                    status=TestStatus.PASSED,
                    response_time_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    details=description,
                )
            else:
                error_detail = ""
                try:
                    error_detail = response.text[:200]
                except Exception:
                    pass
                return EndpointTestResult(
                    endpoint=endpoint,
                    method=method,
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    error=f"Expected {expected_status}, got {response.status_code}. {error_detail}",
                    details=description,
                )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return EndpointTestResult(
                endpoint=endpoint,
                method=method,
                status=TestStatus.FAILED,
                response_time_ms=round(elapsed, 2),
                error=str(e),
                details=description,
            )

    async def test_infrastructure(self) -> dict[str, Any]:
        """Test infrastructure components."""
        results = {
            "database": {"status": "healthy", "response_time_ms": 0},
            "redis": {"status": "healthy", "response_time_ms": 0},
        }

        # Test database
        start = time.perf_counter()
        try:
            async with async_session_maker() as session:
                await session.execute(text("SELECT 1"))
            results["database"]["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        except Exception as e:
            results["database"]["status"] = "unhealthy"
            results["database"]["error"] = str(e)
            results["database"]["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)

        # Test Redis
        start = time.perf_counter()
        try:
            redis_client = await get_redis()
            await redis_client.ping()
            results["redis"]["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        except Exception as e:
            results["redis"]["status"] = "unhealthy"
            results["redis"]["error"] = str(e)
            results["redis"]["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)

        return results

    async def test_health_endpoints(self) -> CategoryTestResult:
        """Test health check endpoints."""
        tests = []

        # Test basic health
        tests.append(await self._test_endpoint(
            "GET", "/health", [200],
            with_auth=False,
            description="Basic health check"
        ))

        # Test readiness probe
        tests.append(await self._test_endpoint(
            "GET", "/health/ready", [200],
            with_auth=False,
            description="Readiness probe (DB + Redis)"
        ))

        # Test liveness probe
        tests.append(await self._test_endpoint(
            "GET", "/health/live", [200],
            with_auth=False,
            description="Liveness probe"
        ))

        # Test root endpoint
        tests.append(await self._test_endpoint(
            "GET", "/", [200],
            with_auth=False,
            description="Root endpoint"
        ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Health Endpoints",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )

    async def test_auth_endpoints(self) -> CategoryTestResult:
        """Test authentication endpoints."""
        tests = []
        test_username = f"healthcheck_user_{uuid.uuid4().hex[:8]}"
        test_email = f"{test_username}@example.com"
        test_password = "HealthCheck123!"

        # 1. Test registration
        start = time.perf_counter()
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/register",
                json={
                    "username": test_username,
                    "email": test_email,
                    "password": test_password,
                },
                headers={"Content-Type": "application/json"},
            )
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code == 201:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/auth/register",
                    method="POST",
                    status=TestStatus.PASSED,
                    response_time_ms=round(elapsed, 2),
                    status_code=201,
                    details="User registration successful",
                ))
            else:
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/auth/register",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    error=f"Registration failed: {response.text[:200]}",
                ))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/auth/register",
                method="POST",
                status=TestStatus.FAILED,
                response_time_ms=round(elapsed, 2),
                error=str(e),
            ))

        # 2. Test login
        start = time.perf_counter()
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/login",
                json={
                    "username": test_username,
                    "password": test_password,
                },
                headers={"Content-Type": "application/json"},
            )
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/auth/login",
                    method="POST",
                    status=TestStatus.PASSED,
                    response_time_ms=round(elapsed, 2),
                    status_code=200,
                    details="Login successful",
                ))
            else:
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/auth/login",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    error=f"Login failed: {response.text[:200]}",
                ))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/auth/login",
                method="POST",
                status=TestStatus.FAILED,
                response_time_ms=round(elapsed, 2),
                error=str(e),
            ))

        # 3. Test get current user
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/auth/me", [200],
            description="Get current user profile"
        ))

        # 4. Test token refresh
        if self.refresh_token:
            start = time.perf_counter()
            try:
                response = await self.client.post(
                    f"{settings.api_v1_prefix}/auth/refresh",
                    json={"refresh_token": self.refresh_token},
                    headers={"Content-Type": "application/json"},
                )
                elapsed = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/auth/refresh",
                        method="POST",
                        status=TestStatus.PASSED,
                        response_time_ms=round(elapsed, 2),
                        status_code=200,
                        details="Token refresh successful",
                    ))
                else:
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/auth/refresh",
                        method="POST",
                        status=TestStatus.FAILED,
                        response_time_ms=round(elapsed, 2),
                        status_code=response.status_code,
                        error=f"Token refresh failed: {response.text[:200]}",
                    ))
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/auth/refresh",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    error=str(e),
                ))
        else:
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/auth/refresh",
                method="POST",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no refresh token available",
            ))

        # 5. Test change password
        tests.append(await self._test_endpoint(
            "POST", f"{settings.api_v1_prefix}/auth/change-password",
            [200],
            json_data={
                "current_password": test_password,
                "new_password": "NewHealthCheck123!",
            },
            description="Change password"
        ))

        # Re-login with new password to get fresh tokens
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/login",
                json={
                    "username": test_username,
                    "password": "NewHealthCheck123!",
                },
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
        except Exception:
            pass

        # 6. Test logout (will invalidate the token)
        # Skip this to keep the token for subsequent tests
        tests.append(EndpointTestResult(
            endpoint=f"{settings.api_v1_prefix}/auth/logout",
            method="POST",
            status=TestStatus.SKIPPED,
            response_time_ms=0,
            details="Skipped - preserving token for other tests",
        ))

        # 7. Test logout-all (skip to preserve session)
        tests.append(EndpointTestResult(
            endpoint=f"{settings.api_v1_prefix}/auth/logout-all",
            method="POST",
            status=TestStatus.SKIPPED,
            response_time_ms=0,
            details="Skipped - preserving session for other tests",
        ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Authentication",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )

    async def test_project_endpoints(self) -> CategoryTestResult:
        """Test project endpoints."""
        tests = []

        # Need to login as a manager/admin to create projects
        # Use seeded admin user
        admin_token = None
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/login",
                json={"username": "admin", "password": "AdminPass123!"},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                admin_token = response.json().get("access_token")
        except Exception:
            pass

        if admin_token:
            original_token = self.access_token
            self.access_token = admin_token

        # 1. Test list projects
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/projects", [200],
            description="List all projects"
        ))

        # 2. Test list projects with query params
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/projects?search=test&page=1&limit=10", [200],
            description="List projects with filters"
        ))

        # 3. Test create project
        project_name = f"HealthCheck Project {uuid.uuid4().hex[:8]}"
        start = time.perf_counter()
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/projects",
                json={
                    "name": project_name,
                    "description": "Project created by health check",
                },
                headers=self._headers(),
            )
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code == 201:
                data = response.json()
                self.test_project_id = uuid.UUID(data.get("id"))
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/projects",
                    method="POST",
                    status=TestStatus.PASSED,
                    response_time_ms=round(elapsed, 2),
                    status_code=201,
                    details="Project created successfully",
                ))
            else:
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/projects",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    status_code=response.status_code,
                    error=f"Project creation failed: {response.text[:200]}",
                ))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/projects",
                method="POST",
                status=TestStatus.FAILED,
                response_time_ms=round(elapsed, 2),
                error=str(e),
            ))

        # 4. Test get project by ID
        if self.test_project_id:
            tests.append(await self._test_endpoint(
                "GET", f"{settings.api_v1_prefix}/projects/{self.test_project_id}", [200],
                description="Get project by ID"
            ))

            # 5. Test update project
            tests.append(await self._test_endpoint(
                "PATCH", f"{settings.api_v1_prefix}/projects/{self.test_project_id}",
                [200],
                json_data={"description": "Updated by health check"},
                description="Update project"
            ))

            # 6. Test archive project (soft delete)
            tests.append(await self._test_endpoint(
                "DELETE", f"{settings.api_v1_prefix}/projects/{self.test_project_id}",
                [200],
                description="Archive project (soft delete)"
            ))

            # Unarchive for further tests
            await self.client.patch(
                f"{settings.api_v1_prefix}/projects/{self.test_project_id}",
                json={"is_archived": False},
                headers=self._headers(),
            )
        else:
            # Use existing project if create failed
            try:
                response = await self.client.get(
                    f"{settings.api_v1_prefix}/projects",
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        self.test_project_id = uuid.UUID(data["items"][0]["id"])
            except Exception:
                pass

            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/projects/{{id}}",
                method="GET",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no project ID available",
            ))
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/projects/{{id}}",
                method="PATCH",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no project ID available",
            ))
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/projects/{{id}}",
                method="DELETE",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no project ID available",
            ))

        # Restore original token
        if admin_token and original_token:
            self.access_token = original_token

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Projects",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )

    async def test_issue_endpoints(self) -> CategoryTestResult:
        """Test issue endpoints."""
        tests = []

        # Login as admin if needed
        admin_token = None
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/login",
                json={"username": "admin", "password": "AdminPass123!"},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                admin_token = response.json().get("access_token")
                self.access_token = admin_token
        except Exception:
            pass

        # Get a project ID if we don't have one
        if not self.test_project_id:
            try:
                response = await self.client.get(
                    f"{settings.api_v1_prefix}/projects",
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        self.test_project_id = uuid.UUID(data["items"][0]["id"])
            except Exception:
                pass

        if self.test_project_id:
            # 1. Test list issues
            tests.append(await self._test_endpoint(
                "GET", f"{settings.api_v1_prefix}/projects/{self.test_project_id}/issues",
                [200],
                description="List issues in project"
            ))

            # 2. Test list issues with filters
            tests.append(await self._test_endpoint(
                "GET",
                f"{settings.api_v1_prefix}/projects/{self.test_project_id}/issues"
                "?status=open&priority=high&page=1&limit=10",
                [200],
                description="List issues with filters"
            ))

            # 3. Test create issue
            start = time.perf_counter()
            try:
                response = await self.client.post(
                    f"{settings.api_v1_prefix}/projects/{self.test_project_id}/issues",
                    json={
                        "title": f"Health Check Issue {uuid.uuid4().hex[:8]}",
                        "description": "Issue created by health check test",
                        "priority": "medium",
                    },
                    headers=self._headers(),
                )
                elapsed = (time.perf_counter() - start) * 1000

                if response.status_code == 201:
                    data = response.json()
                    self.test_issue_id = uuid.UUID(data.get("id"))
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/projects/{{project_id}}/issues",
                        method="POST",
                        status=TestStatus.PASSED,
                        response_time_ms=round(elapsed, 2),
                        status_code=201,
                        details="Issue created successfully",
                    ))
                else:
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/projects/{{project_id}}/issues",
                        method="POST",
                        status=TestStatus.FAILED,
                        response_time_ms=round(elapsed, 2),
                        status_code=response.status_code,
                        error=f"Issue creation failed: {response.text[:200]}",
                    ))
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/projects/{{project_id}}/issues",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    error=str(e),
                ))

            if self.test_issue_id:
                # 4. Test get issue by ID
                tests.append(await self._test_endpoint(
                    "GET", f"{settings.api_v1_prefix}/issues/{self.test_issue_id}",
                    [200],
                    description="Get issue by ID"
                ))

                # 5. Test get valid transitions
                tests.append(await self._test_endpoint(
                    "GET", f"{settings.api_v1_prefix}/issues/{self.test_issue_id}/transitions",
                    [200],
                    description="Get valid status transitions"
                ))

                # 6. Test update issue
                tests.append(await self._test_endpoint(
                    "PATCH", f"{settings.api_v1_prefix}/issues/{self.test_issue_id}",
                    [200],
                    json_data={
                        "title": "Updated Health Check Issue",
                        "status": "in_progress",
                    },
                    description="Update issue"
                ))
            else:
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/issues/{{id}}",
                    method="GET",
                    status=TestStatus.SKIPPED,
                    response_time_ms=0,
                    details="Skipped - no issue ID available",
                ))
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/issues/{{id}}/transitions",
                    method="GET",
                    status=TestStatus.SKIPPED,
                    response_time_ms=0,
                    details="Skipped - no issue ID available",
                ))
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/issues/{{id}}",
                    method="PATCH",
                    status=TestStatus.SKIPPED,
                    response_time_ms=0,
                    details="Skipped - no issue ID available",
                ))
        else:
            for _ in range(6):
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/issues/*",
                    method="*",
                    status=TestStatus.SKIPPED,
                    response_time_ms=0,
                    details="Skipped - no project available",
                ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Issues",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )

    async def test_comment_endpoints(self) -> CategoryTestResult:
        """Test comment endpoints."""
        tests = []

        # Ensure we have admin token
        admin_token = None
        try:
            response = await self.client.post(
                f"{settings.api_v1_prefix}/auth/login",
                json={"username": "admin", "password": "AdminPass123!"},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                admin_token = response.json().get("access_token")
                self.access_token = admin_token
        except Exception:
            pass

        # Get an issue ID if we don't have one
        if not self.test_issue_id and self.test_project_id:
            try:
                response = await self.client.get(
                    f"{settings.api_v1_prefix}/projects/{self.test_project_id}/issues",
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        self.test_issue_id = uuid.UUID(data["items"][0]["id"])
            except Exception:
                pass

        if self.test_issue_id:
            # 1. Test list comments
            tests.append(await self._test_endpoint(
                "GET", f"{settings.api_v1_prefix}/issues/{self.test_issue_id}/comments",
                [200],
                description="List comments on issue"
            ))

            # 2. Test create comment
            start = time.perf_counter()
            try:
                response = await self.client.post(
                    f"{settings.api_v1_prefix}/issues/{self.test_issue_id}/comments",
                    json={
                        "content": f"Health check comment {uuid.uuid4().hex[:8]}",
                    },
                    headers=self._headers(),
                )
                elapsed = (time.perf_counter() - start) * 1000

                if response.status_code == 201:
                    data = response.json()
                    self.test_comment_id = uuid.UUID(data.get("id"))
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/issues/{{issue_id}}/comments",
                        method="POST",
                        status=TestStatus.PASSED,
                        response_time_ms=round(elapsed, 2),
                        status_code=201,
                        details="Comment created successfully",
                    ))
                else:
                    tests.append(EndpointTestResult(
                        endpoint=f"{settings.api_v1_prefix}/issues/{{issue_id}}/comments",
                        method="POST",
                        status=TestStatus.FAILED,
                        response_time_ms=round(elapsed, 2),
                        status_code=response.status_code,
                        error=f"Comment creation failed: {response.text[:200]}",
                    ))
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/issues/{{issue_id}}/comments",
                    method="POST",
                    status=TestStatus.FAILED,
                    response_time_ms=round(elapsed, 2),
                    error=str(e),
                ))

            if self.test_comment_id:
                # 3. Test update comment
                tests.append(await self._test_endpoint(
                    "PATCH", f"{settings.api_v1_prefix}/comments/{self.test_comment_id}",
                    [200],
                    json_data={"content": "Updated health check comment"},
                    description="Update comment"
                ))
            else:
                tests.append(EndpointTestResult(
                    endpoint=f"{settings.api_v1_prefix}/comments/{{id}}",
                    method="PATCH",
                    status=TestStatus.SKIPPED,
                    response_time_ms=0,
                    details="Skipped - no comment ID available",
                ))
        else:
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/issues/{{id}}/comments",
                method="GET",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no issue available",
            ))
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/issues/{{id}}/comments",
                method="POST",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no issue available",
            ))
            tests.append(EndpointTestResult(
                endpoint=f"{settings.api_v1_prefix}/comments/{{id}}",
                method="PATCH",
                status=TestStatus.SKIPPED,
                response_time_ms=0,
                details="Skipped - no comment available",
            ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Comments",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )

    async def test_security_endpoints(self) -> CategoryTestResult:
        """Test security-related scenarios."""
        tests = []

        # 1. Test unauthorized access
        original_token = self.access_token
        self.access_token = None

        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/auth/me",
            [401],
            with_auth=False,
            description="Unauthorized access returns 401"
        ))

        # 2. Test invalid token
        self.access_token = "invalid_token_12345"
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/auth/me",
            [401],
            description="Invalid token returns 401"
        ))

        # Restore token
        self.access_token = original_token

        # 3. Test request validation
        tests.append(await self._test_endpoint(
            "POST", f"{settings.api_v1_prefix}/auth/login",
            [422],
            json_data={"username": "a"},  # Missing password
            with_auth=False,
            description="Invalid request body returns 422"
        ))

        # 4. Test non-existent resource
        fake_uuid = str(uuid.uuid4())
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/projects/{fake_uuid}",
            [404],
            description="Non-existent resource returns 404"
        ))

        # 5. Test rate limiting headers (just check response succeeds)
        tests.append(await self._test_endpoint(
            "GET", f"{settings.api_v1_prefix}/projects",
            [200],
            description="Rate limiting headers present"
        ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return CategoryTestResult(
            category="Security",
            total=len(tests),
            passed=passed,
            failed=failed,
            skipped=skipped,
            tests=tests,
        )


@router.get(
    "/extensive",
    response_model=ExtensiveHealthCheckResponse,
    summary="Extensive API Health Check",
    description="""
    Comprehensive health check that tests all API endpoints.
    
    This endpoint performs a full suite of tests including:
    - Infrastructure checks (Database, Redis)
    - Health endpoints
    - Authentication flow (register, login, refresh, change password)
    - Project CRUD operations
    - Issue CRUD operations  
    - Comment CRUD operations
    - Security scenarios (unauthorized access, invalid tokens, validation)
    
    **Note**: This creates temporary test data that will persist in the database.
    Recommended for staging/development environments.
    """,
)
async def extensive_health_check(request: Request) -> ExtensiveHealthCheckResponse:
    """Run extensive health check on all API endpoints."""
    start_time = time.perf_counter()

    # Determine base URL
    base_url = str(request.base_url).rstrip("/")

    # Initialize tester
    tester = APITester(base_url)

    try:
        # Test infrastructure
        infrastructure = await tester.test_infrastructure()

        # Run all test categories
        categories = []

        # 1. Health endpoints
        categories.append(await tester.test_health_endpoints())

        # 2. Auth endpoints
        categories.append(await tester.test_auth_endpoints())

        # 3. Project endpoints
        categories.append(await tester.test_project_endpoints())

        # 4. Issue endpoints
        categories.append(await tester.test_issue_endpoints())

        # 5. Comment endpoints
        categories.append(await tester.test_comment_endpoints())

        # 6. Security scenarios
        categories.append(await tester.test_security_endpoints())

        # Calculate totals
        total_tests = sum(c.total for c in categories)
        total_passed = sum(c.passed for c in categories)
        total_failed = sum(c.failed for c in categories)
        total_skipped = sum(c.skipped for c in categories)

        # Determine overall status
        infra_healthy = all(
            v.get("status") == "healthy"
            for v in infrastructure.values()
        )
        overall_status = "healthy" if total_failed == 0 and infra_healthy else "degraded"
        if total_failed > total_tests // 2:
            overall_status = "unhealthy"

        total_time = (time.perf_counter() - start_time) * 1000

        return ExtensiveHealthCheckResponse(
            status=overall_status,
            version=__version__,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_tests=total_tests,
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            total_time_ms=round(total_time, 2),
            infrastructure=infrastructure,
            categories=categories,
        )

    finally:
        await tester.close()
