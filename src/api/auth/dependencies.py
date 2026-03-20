"""FastAPI dependencies for authentication / authorization."""

import logging

import jwt as pyjwt
from fastapi import Depends, HTTPException, status

from src.api.auth.jwt import decode_access_token
from src.api.auth.oauth2 import oauth2_scheme

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
