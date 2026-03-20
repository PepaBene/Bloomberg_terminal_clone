"""JWT token creation and validation."""

import logging
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from src.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = settings.JWT_ALGORITHM
SECRET_KEY = settings.JWT_SECRET_KEY
EXPIRY_MINUTES = settings.JWT_EXPIRY_MINUTES


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Parameters
    ----------
    data : dict
        Payload claims to encode (must include ``sub``).
    expires_delta : timedelta, optional
        Custom expiry.  Falls back to ``JWT_EXPIRY_MINUTES`` from config.

    Returns
    -------
    str
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=EXPIRY_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token.

    Raises
    ------
    pyjwt.ExpiredSignatureError
        Token has expired.
    pyjwt.InvalidTokenError
        Token is malformed or signature is invalid.
    """
    return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
