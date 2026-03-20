"""OAuth 2.0 bearer token scheme for FastAPI."""

from fastapi.security import OAuth2PasswordBearer

# Token URL that clients POST to with username/password to receive a JWT.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
