"""Role-based access control (RBAC) permission system."""

from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import Request

from app.core.exceptions import AuthorizationError
from app.models.user import User, UserRole


class Permission(str, Enum):
    """Available permissions in the system."""

    # Project permissions
    VIEW_PROJECTS = "view_projects"
    CREATE_PROJECT = "create_project"
    EDIT_PROJECT = "edit_project"
    ARCHIVE_PROJECT = "archive_project"

    # Issue permissions
    VIEW_ISSUES = "view_issues"
    CREATE_ISSUE = "create_issue"
    EDIT_ISSUE = "edit_issue"
    CHANGE_ASSIGNEE = "change_assignee"

    # Comment permissions
    VIEW_COMMENTS = "view_comments"
    ADD_COMMENT = "add_comment"
    EDIT_COMMENT = "edit_comment"

    # User management
    VIEW_USERS = "view_users"
    MANAGE_USERS = "manage_users"


# Role to permission mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.DEVELOPER: {
        Permission.VIEW_PROJECTS,
        Permission.VIEW_ISSUES,
        Permission.CREATE_ISSUE,
        Permission.VIEW_COMMENTS,
        Permission.ADD_COMMENT,
        Permission.VIEW_USERS,
    },
    UserRole.MANAGER: {
        Permission.VIEW_PROJECTS,
        Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT,
        Permission.ARCHIVE_PROJECT,
        Permission.VIEW_ISSUES,
        Permission.CREATE_ISSUE,
        Permission.EDIT_ISSUE,
        Permission.CHANGE_ASSIGNEE,
        Permission.VIEW_COMMENTS,
        Permission.ADD_COMMENT,
        Permission.EDIT_COMMENT,
        Permission.VIEW_USERS,
    },
    UserRole.ADMIN: set(Permission),  # All permissions
}


def has_permission(user: User, permission: Permission) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user: User to check
        permission: Permission to check for

    Returns:
        True if user has the permission, False otherwise
    """
    if not user or not user.is_active:
        return False

    user_permissions = ROLE_PERMISSIONS.get(user.role, set())
    return permission in user_permissions


def has_any_permission(user: User, permissions: list[Permission]) -> bool:
    """
    Check if a user has any of the specified permissions.

    Args:
        user: User to check
        permissions: List of permissions to check for

    Returns:
        True if user has any of the permissions, False otherwise
    """
    return any(has_permission(user, p) for p in permissions)


def has_all_permissions(user: User, permissions: list[Permission]) -> bool:
    """
    Check if a user has all of the specified permissions.

    Args:
        user: User to check
        permissions: List of permissions to check for

    Returns:
        True if user has all permissions, False otherwise
    """
    return all(has_permission(user, p) for p in permissions)


def get_user_permissions(user: User) -> set[Permission]:
    """
    Get all permissions for a user.

    Args:
        user: User to get permissions for

    Returns:
        Set of permissions the user has
    """
    if not user or not user.is_active:
        return set()

    return ROLE_PERMISSIONS.get(user.role, set())


class PermissionChecker:
    """
    Permission checker for use as a FastAPI dependency.

    Usage:
        @router.get("/projects", dependencies=[Depends(PermissionChecker(Permission.VIEW_PROJECTS))])
        async def list_projects(...):
            ...
    """

    def __init__(
        self,
        *permissions: Permission,
        require_all: bool = False,
    ):
        """
        Initialize permission checker.

        Args:
            permissions: Permissions to check for
            require_all: If True, user must have ALL permissions. If False, any one is sufficient.
        """
        self.permissions = list(permissions)
        self.require_all = require_all

    async def __call__(self, request: Request) -> bool:
        """
        Check permissions for the current user.

        Args:
            request: FastAPI request object (must have user set by auth middleware)

        Returns:
            True if permission check passes

        Raises:
            AuthorizationError: If permission check fails
        """
        user: Optional[User] = getattr(request.state, "user", None)

        if not user:
            raise AuthorizationError(message="Authentication required")

        if not user.is_active:
            raise AuthorizationError(message="Account is deactivated")

        if self.require_all:
            has_perms = has_all_permissions(user, self.permissions)
        else:
            has_perms = has_any_permission(user, self.permissions)

        if not has_perms:
            raise AuthorizationError(
                message="You don't have permission to perform this action",
                details=[
                    {
                        "required_permissions": [p.value for p in self.permissions],
                        "user_role": user.role.value,
                    }
                ],
            )

        return True


def require_permission(*permissions: Permission, require_all: bool = False):
    """
    Decorator to require specific permissions for an endpoint.

    Usage:
        @router.get("/projects")
        @require_permission(Permission.VIEW_PROJECTS)
        async def list_projects(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get request from kwargs or args
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                user: Optional[User] = getattr(request.state, "user", None)

                if not user:
                    raise AuthorizationError(message="Authentication required")

                if not user.is_active:
                    raise AuthorizationError(message="Account is deactivated")

                if require_all:
                    has_perms = has_all_permissions(user, list(permissions))
                else:
                    has_perms = has_any_permission(user, list(permissions))

                if not has_perms:
                    raise AuthorizationError(
                        message="You don't have permission to perform this action"
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(*roles: UserRole):
    """
    Decorator to require specific roles for an endpoint.

    Usage:
        @router.delete("/users/{user_id}")
        @require_role(UserRole.ADMIN)
        async def delete_user(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                user: Optional[User] = getattr(request.state, "user", None)

                if not user:
                    raise AuthorizationError(message="Authentication required")

                if not user.is_active:
                    raise AuthorizationError(message="Account is deactivated")

                if user.role not in roles:
                    raise AuthorizationError(
                        message="You don't have permission to perform this action",
                        details=[
                            {
                                "required_roles": [r.value for r in roles],
                                "user_role": user.role.value,
                            }
                        ],
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Pre-configured permission checkers for common use cases
ViewProjects = PermissionChecker(Permission.VIEW_PROJECTS)
CreateProject = PermissionChecker(Permission.CREATE_PROJECT)
EditProject = PermissionChecker(Permission.EDIT_PROJECT)
ArchiveProject = PermissionChecker(Permission.ARCHIVE_PROJECT)

ViewIssues = PermissionChecker(Permission.VIEW_ISSUES)
CreateIssue = PermissionChecker(Permission.CREATE_ISSUE)
EditIssue = PermissionChecker(Permission.EDIT_ISSUE)
ChangeAssignee = PermissionChecker(Permission.CHANGE_ASSIGNEE)

ViewComments = PermissionChecker(Permission.VIEW_COMMENTS)
AddComment = PermissionChecker(Permission.ADD_COMMENT)
EditComment = PermissionChecker(Permission.EDIT_COMMENT)

ViewUsers = PermissionChecker(Permission.VIEW_USERS)
ManageUsers = PermissionChecker(Permission.MANAGE_USERS)
