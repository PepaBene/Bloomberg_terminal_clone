"""FastAPI dependencies for injection."""

import logging
from collections.abc import AsyncGenerator

from fastapi import Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.common import PaginationParams

logger = logging.getLogger(__name__)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async for session in get_db():
        yield session


def get_pagination(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
) -> PaginationParams:
    """Build pagination parameters from query string."""
    return PaginationParams(page=page, page_size=page_size)


def get_request_id(request: Request) -> str:
    """Extract the request ID assigned by middleware."""
    return request.state.request_id


async def get_optional_user(request: Request):
    """Return the current user payload if a valid Bearer token is present, else None.

    This dependency allows endpoints to function both with and without
    authentication — useful during development and for gradual auth rollout.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        from src.api.auth.dependencies import get_current_user

        token = auth_header.split(" ", 1)[1]
        return await get_current_user(token)
    except Exception:
        logger.debug("Optional auth: token present but invalid; continuing as anonymous.")
        return None
