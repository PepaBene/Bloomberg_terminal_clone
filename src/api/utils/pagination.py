"""Cursor-based pagination extension (Spec 17.2).

Extends the existing offset-based PaginatedResponse with cursor-based
pagination.  The cursor is a base64-encoded string of the last record's
sort key + ID, enabling efficient keyset pagination for large result sets.

The offset-based approach (``page`` / ``page_size``) is kept as the default
for backward compatibility.  Cursor-based pagination is activated by
including ``?cursor=<token>`` in the request.
"""

import base64
import json
import logging
import uuid
from typing import Any

from src.schemas.common import PaginatedMeta, PaginationParams

logger = logging.getLogger(__name__)


def encode_cursor(sort_value: Any, record_id: str) -> str:
    """Encode a pagination cursor from sort value and record ID.

    Parameters
    ----------
    sort_value : Any
        The value of the field being sorted by for the last record.
    record_id : str
        The unique ID of the last record.

    Returns
    -------
    str
        Base64-encoded cursor token.
    """
    payload = json.dumps({"v": str(sort_value), "id": str(record_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode a pagination cursor.

    Returns
    -------
    tuple[str, str]
        (sort_value, record_id)

    Raises
    ------
    ValueError
        If the cursor is malformed.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return payload["v"], payload["id"]
    except (json.JSONDecodeError, KeyError, Exception) as e:
        raise ValueError(f"Invalid cursor: {e}") from e


def build_cursor_meta(
    items: list,
    total_count: int,
    page_size: int,
    sort_field: str,
    id_field: str = "id",
) -> dict:
    """Build pagination metadata including cursor tokens.

    Parameters
    ----------
    items : list
        The current page of results (dicts or objects).
    total_count : int
        Total number of records matching the query.
    page_size : int
        Requested page size.
    sort_field : str
        The field name used for sorting.
    id_field : str
        The field name for the unique record ID.

    Returns
    -------
    dict
        Metadata including ``next_cursor`` and ``prev_cursor``.
    """
    meta: dict[str, Any] = {
        "total_count": total_count,
        "page_size": page_size,
        "has_more": len(items) == page_size,
    }

    if items:
        last = items[-1]
        if isinstance(last, dict):
            last_sort = last.get(sort_field, "")
            last_id = last.get(id_field, "")
        else:
            last_sort = getattr(last, sort_field, "")
            last_id = getattr(last, id_field, "")
        meta["next_cursor"] = encode_cursor(last_sort, last_id)

        first = items[0]
        if isinstance(first, dict):
            first_sort = first.get(sort_field, "")
            first_id = first.get(id_field, "")
        else:
            first_sort = getattr(first, sort_field, "")
            first_id = getattr(first, id_field, "")
        meta["prev_cursor"] = encode_cursor(first_sort, first_id)

    return meta


def build_paginated_meta(
    total_count: int,
    pagination: PaginationParams,
) -> PaginatedMeta:
    """Build standard paginated response metadata."""
    return PaginatedMeta(
        request_id=str(uuid.uuid4()),
        total_count=total_count,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
    )
