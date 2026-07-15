"""Password hashing utilities.

Previously `auth.py` compared `hashed_password` with a plaintext `==`
(explicitly flagged in its own NOTE comment as a placeholder). This is the
real bcrypt-backed implementation.
"""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/legacy (non-bcrypt) hash -- never match.
        return False
