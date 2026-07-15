"""Authentication endpoints for registration, login, and user info."""

import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user
from src.api.auth.jwt import create_access_token
from src.api.auth.security import hash_password, verify_password
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


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    email: str
    role: str

    model_config = {"from_attributes": True}


# -- Endpoints ---------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new user account with a bcrypt-hashed password.

    New accounts default to the VIEWER role -- promoting to ANALYST/ADMIN
    is an out-of-band admin action, not self-service.
    """
    existing = await session.execute(
        select(User).where(or_(User.username == body.username, User.email == body.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username or email already registered")

    user = User(
        user_id=uuid.uuid4(),
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role="VIEWER",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    logger.info("User '%s' registered.", user.username)
    return RegisterResponse(
        user_id=user.user_id, username=user.username, email=user.email, role=user.role,
    )


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

    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
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
