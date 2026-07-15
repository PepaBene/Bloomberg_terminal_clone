"""FastAPI dependencies for authentication / authorization."""

import logging

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.jwt import decode_access_token
from src.api.auth.oauth2 import oauth2_scheme
from src.api.deps import get_session
from src.models.auth import User

logger = logging.getLogger(__name__)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode the bearer token and return the user payload.

    The returned dict contains at least ``sub`` (user-id / username) and
    ``role`` (e.g. ADMIN, ANALYST, VIEWER, API_SERVICE).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub: str | None = payload.get("sub")
        if sub is None:
            raise credentials_exception
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise credentials_exception


async def get_current_active_user(
    payload: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the bearer token's ``sub`` (username) to a real ``User`` row.

    Endpoints that need the caller's actual identity (a real ``user_id``
    UUID, not just the token payload) should depend on this instead of
    ``get_current_user`` -- e.g. anything writing ``user_id``/``analyst_id``
    into a FK'd column (M-004/M-005).
    """
    username = payload.get("sub")
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
