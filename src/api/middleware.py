"""Request middleware: request ID, timing, error handling."""

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID and measure processing time."""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.perf_counter()

        response: Response = await call_next(request)

        processing_time = int(
            (time.perf_counter() - request.state.start_time) * 1000
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = str(processing_time)

        return response
