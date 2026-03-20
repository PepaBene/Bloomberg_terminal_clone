"""Role-Based Access Control (RBAC) dependencies."""

from fastapi import Depends, HTTPException, status

from src.api.auth.dependencies import get_current_user

# Role hierarchy (higher index = more privilege)
ROLE_HIERARCHY = {
    "VIEWER": 0,
    "ANALYST": 1,
    "API_SERVICE": 2,
    "ADMIN": 3,
}


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that checks the user's role.

    Usage::

        @router.post("/admin-only", dependencies=[Depends(require_role("ADMIN"))])
        async def admin_endpoint(): ...
    """

    async def _check_role(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role", "VIEWER")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not permitted. Required: {allowed_roles}",
            )
        return current_user

    return _check_role


# Pre-built convenience dependencies
require_admin = require_role("ADMIN")
require_analyst = require_role("ADMIN", "ANALYST")
require_writer = require_role("ADMIN", "ANALYST", "API_SERVICE")
