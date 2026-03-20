"""Authentication endpoints for login and user info."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user
from src.api.auth.jwt import create_access_token
from src.api.deps import get_session
from src.config import settings
from src.models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# -- Schemas -----------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    sub: str
    role: str


# -- Endpoints ---------------------------------------------------------------

@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with username/password and receive a JWT access token.

    The token should be passed as a Bearer token in the ``Authorization``
    header for subsequent requests that require authentication.
    """
    result = await session.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # NOTE: In production, replace this plaintext comparison with bcrypt
    # verification (e.g., bcrypt.checkpw(password, user.hashed_password)).
    if user.hashed_password != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    )
    logger.info("User '%s' authenticated successfully.", user.username)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the identity and role of the currently authenticated user."""
    return UserInfo(
        sub=current_user.get("sub", ""),
        role=current_user.get("role", "VIEWER"),
    )
