#!/usr/bin/env python
"""
Seed data script for development and testing.

Usage:
    python scripts/seed_data.py

This script creates:
- Default admin user
- Sample manager and developer users
- Sample projects
- Sample issues with various statuses
- Sample comments
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.config import settings
from app.core.security import hash_password
from app.database import async_session_maker, init_db
from app.models.comment import Comment
from app.models.issue import Issue, IssuePriority, IssueStatus
from app.models.project import Project
from app.models.user import User, UserRole


# Seed data
USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": UserRole.ADMIN,
    },
    {
        "username": "manager1",
        "email": "manager1@example.com",
        "password": "ManagerPass123!",
        "role": UserRole.MANAGER,
    },
    {
        "username": "manager2",
        "email": "manager2@example.com",
        "password": "ManagerPass123!",
        "role": UserRole.MANAGER,
    },
    {
        "username": "dev1",
        "email": "dev1@example.com",
        "password": "DevPass123!",
        "role": UserRole.DEVELOPER,
    },
    {
        "username": "dev2",
        "email": "dev2@example.com",
        "password": "DevPass123!",
        "role": UserRole.DEVELOPER,
    },
    {
        "username": "dev3",
        "email": "dev3@example.com",
        "password": "DevPass123!",
        "role": UserRole.DEVELOPER,
    },
]

PROJECTS = [
    {
        "name": "Bug Tracker API",
        "description": "Internal bug tracking system API for development teams.",
    },
    {
        "name": "Mobile App",
        "description": "Cross-platform mobile application for iOS and Android.",
    },
    {
        "name": "Web Dashboard",
        "description": "Admin dashboard for monitoring and analytics.",
    },
    {
        "name": "Data Pipeline",
        "description": "ETL pipeline for data processing and warehousing.",
    },
]

ISSUES = [
    {
        "title": "Login fails with special characters in password",
        "description": "When a user's password contains special characters like `<` or `>`, the login API returns a 500 error instead of authenticating properly.",
        "status": IssueStatus.OPEN,
        "priority": IssuePriority.HIGH,
    },
    {
        "title": "API response time is slow for large datasets",
        "description": "The `/api/projects` endpoint takes more than 5 seconds to respond when there are more than 100 projects.",
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.MEDIUM,
    },
    {
        "title": "Missing validation for email format",
        "description": "The registration endpoint accepts invalid email formats without proper validation.",
        "status": IssueStatus.RESOLVED,
        "priority": IssuePriority.LOW,
    },
    {
        "title": "Security vulnerability in file upload",
        "description": "Critical security issue: The file upload endpoint allows uploading executable files without proper sanitization.",
        "status": IssueStatus.OPEN,
        "priority": IssuePriority.CRITICAL,
    },
    {
        "title": "Mobile app crashes on startup",
        "description": "The mobile app crashes immediately after launch on iOS 17 devices.",
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.CRITICAL,
    },
    {
        "title": "Dashboard charts not rendering correctly",
        "description": "The analytics charts on the dashboard show incorrect data and sometimes fail to render.",
        "status": IssueStatus.OPEN,
        "priority": IssuePriority.MEDIUM,
    },
    {
        "title": "Data sync issues between services",
        "description": "Data is not properly synchronized between the API and the data warehouse, causing inconsistencies.",
        "status": IssueStatus.REOPENED,
        "priority": IssuePriority.HIGH,
    },
    {
        "title": "Implement dark mode support",
        "description": "Add dark mode theme option to the web dashboard for better user experience.",
        "status": IssueStatus.OPEN,
        "priority": IssuePriority.LOW,
    },
    {
        "title": "Optimize database queries",
        "description": "Several database queries are not using indexes efficiently, causing performance issues.",
        "status": IssueStatus.CLOSED,
        "priority": IssuePriority.MEDIUM,
    },
    {
        "title": "Add pagination to all list endpoints",
        "description": "Implement consistent pagination across all API list endpoints for better performance.",
        "status": IssueStatus.CLOSED,
        "priority": IssuePriority.MEDIUM,
    },
]

COMMENTS = [
    "I can reproduce this issue. Looking into it now.",
    "This seems to be related to the recent deployment.",
    "Fixed in the latest commit. Please review the PR.",
    "Confirmed working after the fix. Closing this issue.",
    "This needs more investigation. Adding to the backlog.",
    "Can we get more details about the environment this occurred in?",
    "Duplicates issue #42. Please check that one for updates.",
    "Added a unit test to prevent regression.",
]


async def seed_database():
    """Seed the database with sample data."""
    print("Initializing database...")
    await init_db()

    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping...")
            return

        print("Creating users...")
        users = {}
        for user_data in USERS:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
            )
            session.add(user)
            users[user_data["username"]] = user

        await session.flush()

        print("Creating projects...")
        projects = []
        managers = [users["manager1"], users["manager2"]]
        for i, project_data in enumerate(PROJECTS):
            project = Project(
                name=project_data["name"],
                description=project_data["description"],
                created_by_id=managers[i % len(managers)].id,
            )
            session.add(project)
            projects.append(project)

        await session.flush()

        print("Creating issues...")
        developers = [users["dev1"], users["dev2"], users["dev3"]]
        issues = []
        for i, issue_data in enumerate(ISSUES):
            project = projects[i % len(projects)]
            reporter = developers[i % len(developers)]
            assignee = developers[(i + 1) % len(developers)] if i % 2 == 0 else None

            issue = Issue(
                title=issue_data["title"],
                description=issue_data["description"],
                status=issue_data["status"],
                priority=issue_data["priority"],
                project_id=project.id,
                reporter_id=reporter.id,
                assignee_id=assignee.id if assignee else None,
                due_date=date.today() + timedelta(days=7 + i * 3) if i % 3 == 0 else None,
            )
            session.add(issue)
            issues.append(issue)

        await session.flush()

        print("Creating comments...")
        all_users = list(users.values())
        for i, issue in enumerate(issues):
            # Add 1-3 comments per issue
            num_comments = (i % 3) + 1
            for j in range(num_comments):
                comment = Comment(
                    content=COMMENTS[(i + j) % len(COMMENTS)],
                    issue_id=issue.id,
                    author_id=all_users[(i + j) % len(all_users)].id,
                )
                session.add(comment)

        await session.commit()

        print("\n" + "=" * 50)
        print("Database seeded successfully!")
        print("=" * 50)
        print("\nCreated:")
        print(f"  - {len(USERS)} users")
        print(f"  - {len(PROJECTS)} projects")
        print(f"  - {len(ISSUES)} issues")
        print(f"  - Multiple comments")
        print("\nDefault credentials:")
        print("  Admin:    admin / AdminPass123!")
        print("  Manager:  manager1 / ManagerPass123!")
        print("  Developer: dev1 / DevPass123!")


if __name__ == "__main__":
    asyncio.run(seed_database())
