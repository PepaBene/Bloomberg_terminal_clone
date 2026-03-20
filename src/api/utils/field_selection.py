"""Field selection middleware for API responses (Spec 17.2).

Supports selecting specific fields in the response:
    ?fields=entity_id,legal_name,status

When ``fields`` is present, the response JSON is pruned to include only
the requested fields (plus ``meta`` for paginated responses).
"""

import json
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


def _prune_fields(obj, fields: set[str]):
    """Recursively prune a dict/list to only include the requested fields."""
    if isinstance(obj, dict):
        # If this is a paginated response, keep meta and prune data items
        if "data" in obj and "meta" in obj:
            pruned_data = [_prune_fields(item, fields) for item in obj.get("data", [])]
            return {"data": pruned_data, "meta": obj["meta"]}
        # Regular dict — keep only requested keys
        return {k: v for k, v in obj.items() if k in fields}
    elif isinstance(obj, list):
        return [_prune_fields(item, fields) for item in obj]
    return obj


class FieldSelectionMiddleware(BaseHTTPMiddleware):
    """Middleware that prunes response fields based on ?fields= parameter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        fields_param = request.query_params.get("fields")
        response = await call_next(request)

        if not fields_param:
            return response

        # Only apply to JSON responses
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read and parse the response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else chunk.encode()

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        fields = {f.strip() for f in fields_param.split(",")}
        pruned = _prune_fields(data, fields)

        return Response(
            content=json.dumps(pruned),
            status_code=response.status_code,
            media_type="application/json",
            headers={
                k: v
                for k, v in response.headers.items()
                if k.lower() != "content-length"
            },
        )
