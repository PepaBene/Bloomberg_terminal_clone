"""Tests for authentication and JWT."""

import pytest
from datetime import timedelta

from src.api.auth.jwt import create_access_token, decode_access_token


class TestJWT:
    def test_create_and_decode_token(self):
        """Test JWT round-trip: create token, then decode it."""
        data = {"sub": "testuser", "role": "ANALYST"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        decoded = decode_access_token(token)
        assert decoded["sub"] == "testuser"
        assert decoded["role"] == "ANALYST"

    def test_decode_expired_token(self):
        """Test that expired tokens raise an error."""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        with pytest.raises(Exception):  # jwt.ExpiredSignatureError
            decode_access_token(token)

    def test_decode_invalid_token(self):
        """Test that invalid tokens raise an error."""
        with pytest.raises(Exception):
            decode_access_token("not.a.valid.token")

    def test_token_contains_expiry(self):
        """Test that tokens contain an expiry claim."""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        decoded = decode_access_token(token)
        assert "exp" in decoded

    def test_token_contains_issued_at(self):
        """Test that tokens contain an issued-at claim."""
        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        decoded = decode_access_token(token)
        assert "iat" in decoded

    def test_custom_claims_preserved(self):
        """Test that arbitrary custom claims survive the round-trip."""
        data = {"sub": "admin", "role": "ADMIN", "org": "bloomberg", "level": 5}
        token = create_access_token(data, expires_delta=timedelta(minutes=30))
        decoded = decode_access_token(token)
        assert decoded["sub"] == "admin"
        assert decoded["role"] == "ADMIN"
        assert decoded["org"] == "bloomberg"
        assert decoded["level"] == 5

    def test_default_expiry_used_when_none(self):
        """Test that omitting expires_delta uses the config default."""
        data = {"sub": "testuser"}
        token = create_access_token(data)  # No expires_delta
        decoded = decode_access_token(token)
        assert "exp" in decoded
        # Should not raise — token was just created so it's still valid
