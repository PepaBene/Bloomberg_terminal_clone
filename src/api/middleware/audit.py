"""Request audit logging middleware."""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Logs all API requests for audit compliance."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()

        # Extract auth info if present
        auth_header = request.headers.get("authorization", "")
        user_id = "anonymous"
        if auth_header.startswith("Bearer "):
            # In production, decode JWT here; for now just note it's present
            user_id = "authenticated"

        response = await call_next(request)

        elapsed_ms = (time.time() - start) * 1000
        logger.info(
            "API_AUDIT | %s %s | status=%d | user=%s | %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            user_id,
            elapsed_ms,
        )

        return response
