"""Tests for authentication and JWT."""

import pytest
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.jwt import create_access_token, decode_access_token
from src.api.auth.security import hash_password, verify_password


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


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert hashed != "correct-horse-battery-staple"
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_verify_against_malformed_hash_returns_false(self):
        """A non-bcrypt (e.g. legacy plaintext) hash must never match."""
        assert verify_password("anything", "not-a-real-bcrypt-hash") is False


class TestRegisterAndLogin:
    """POST /auth/register + POST /auth/token, end-to-end (M-004/M-005:
    the real-auth path that research_briefings.py/research_thesis.py now
    require)."""

    @pytest.mark.asyncio
    async def test_register_creates_user(self, client: AsyncClient, session: AsyncSession):
        resp = await client.post("/auth/register", json={
            "username": "new_analyst",
            "email": "new_analyst@test.example",
            "password": "s3cure-pass!",
            "full_name": "New Analyst",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "new_analyst"
        assert data["role"] == "VIEWER"
        assert "password" not in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_username_conflicts(self, client: AsyncClient, session: AsyncSession):
        body = {
            "username": "dupe_analyst", "email": "dupe1@test.example", "password": "pw1234567",
        }
        resp1 = await client.post("/auth/register", json=body)
        assert resp1.status_code == 201

        resp2 = await client.post("/auth/register", json={**body, "email": "dupe2@test.example"})
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_login_with_correct_password_succeeds(self, client: AsyncClient, session: AsyncSession):
        await client.post("/auth/register", json={
            "username": "login_ok", "email": "login_ok@test.example", "password": "right-password",
        })
        resp = await client.post(
            "/auth/token",
            data={"username": "login_ok", "password": "right-password"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_rejected(self, client: AsyncClient, session: AsyncSession):
        await client.post("/auth/register", json={
            "username": "login_bad", "email": "login_bad@test.example", "password": "right-password",
        })
        resp = await client.post(
            "/auth/token",
            data={"username": "login_bad", "password": "wrong-password"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_then_call_protected_endpoint(self, client: AsyncClient, session: AsyncSession):
        """Full loop: register -> login -> use the token on a real M-004/M-005 endpoint."""
        await client.post("/auth/register", json={
            "username": "full_loop", "email": "full_loop@test.example", "password": "loop-password",
        })
        token_resp = await client.post(
            "/auth/token", data={"username": "full_loop", "password": "loop-password"},
        )
        token = token_resp.json()["access_token"]

        resp = await client.get(
            "/v4/research/briefings/today", headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
