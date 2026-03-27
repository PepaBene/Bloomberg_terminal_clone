"""Tests for audit logging middleware and optional auth dependency."""

import logging
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.middleware.audit import AuditLogMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    """Create a minimal FastAPI app with AuditLogMiddleware."""
    app = FastAPI()
    app.add_middleware(AuditLogMiddleware)

    @app.get("/test")
    async def _test_endpoint():
        return {"ok": True}

    @app.get("/error")
    async def _error_endpoint():
        raise ValueError("boom")

    @app.exception_handler(ValueError)
    async def _handle(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=500)

    return app


@pytest.fixture
def app():
    return _build_app()


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# AuditLogMiddleware tests
# ---------------------------------------------------------------------------


class TestAuditLogMiddleware:
    """Verify that the audit middleware logs requests correctly."""

    def test_anonymous_request_logged(self, client, caplog):
        """Requests without auth header are logged as 'anonymous'."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            resp = client.get("/test")
        assert resp.status_code == 200
        assert any("API_AUDIT" in r.message and "anonymous" in r.message for r in caplog.records)

    def test_authenticated_request_logged(self, client, caplog):
        """Requests with Bearer token are logged as 'authenticated'."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            resp = client.get("/test", headers={"Authorization": "Bearer fake.jwt.token"})
        assert resp.status_code == 200
        assert any("API_AUDIT" in r.message and "authenticated" in r.message for r in caplog.records)

    def test_log_includes_method_and_path(self, client, caplog):
        """Log line includes HTTP method and URL path."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            client.get("/test")
        assert any("GET" in r.message and "/test" in r.message for r in caplog.records)

    def test_log_includes_status_code(self, client, caplog):
        """Log line includes response status code."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            client.get("/test")
        assert any("status=200" in r.message for r in caplog.records)

    def test_error_response_logged(self, client, caplog):
        """Even error responses produce an audit log entry."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            resp = client.get("/error")
        assert resp.status_code == 500
        assert any("API_AUDIT" in r.message and "status=500" in r.message for r in caplog.records)

    def test_log_includes_elapsed_ms(self, client, caplog):
        """Log line includes elapsed time in ms."""
        with caplog.at_level(logging.INFO, logger="src.api.middleware.audit"):
            client.get("/test")
        audit_lines = [r.message for r in caplog.records if "API_AUDIT" in r.message]
        assert len(audit_lines) >= 1
        assert "ms" in audit_lines[0]


# ---------------------------------------------------------------------------
# get_optional_user tests
# ---------------------------------------------------------------------------


class TestGetOptionalUser:
    """Tests for the optional auth dependency in deps.py."""

    @pytest.mark.asyncio
    async def test_returns_none_without_auth_header(self):
        """Without an Authorization header, returns None."""
        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}
        # Ensure REQUIRE_AUTH is not set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REQUIRE_AUTH", None)
            result = await get_optional_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_with_non_bearer_header(self):
        """A non-Bearer Authorization header returns None."""
        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REQUIRE_AUTH", None)
            result = await get_optional_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_with_valid_bearer(self):
        """With a Bearer token, attempts JWT decode and returns user string."""
        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid.jwt.token"}

        fake_payload = {"sub": "testuser", "role": "ANALYST"}
        with patch("src.api.deps.get_optional_user.__module__", "src.api.deps"):
            with patch(
                "src.api.auth.dependencies.get_current_user",
                new_callable=AsyncMock,
                return_value=fake_payload,
            ):
                result = await get_optional_user(mock_request)
        assert result == "testuser"

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_token(self):
        """An invalid Bearer token gracefully returns None (not 401)."""
        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer bad.token"}

        with patch(
            "src.api.auth.dependencies.get_current_user",
            new_callable=AsyncMock,
            side_effect=Exception("Invalid token"),
        ):
            result = await get_optional_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_require_auth_raises_401(self):
        """When REQUIRE_AUTH=true and no token, raises HTTPException 401."""
        from fastapi import HTTPException

        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}

        with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_user(mock_request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_auth_false_allows_anonymous(self):
        """When REQUIRE_AUTH=false (default), no token returns None."""
        from src.api.deps import get_optional_user

        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}

        with patch.dict(os.environ, {"REQUIRE_AUTH": "false"}):
            result = await get_optional_user(mock_request)
        assert result is None
