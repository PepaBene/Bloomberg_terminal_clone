"""Common schemas: pagination, filtering, response envelope."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    """Metadata included in every API response."""

    request_id: str = ""
    processing_time_ms: int = 0
    cache_hit: bool = False
    as_of: date | None = None
    data_version: str | None = None
    last_updated: datetime | None = None


class PaginatedMeta(ResponseMeta):
    """Metadata for paginated responses."""

    total_count: int
    page: int
    page_size: int
    total_pages: int
    next_cursor: str | None = None


class APIResponse(BaseModel):
    """Standard API response wrapper."""

    data: Any
    meta: ResponseMeta


class PaginatedResponse(BaseModel):
    """Paginated API response wrapper."""

    data: list[Any]
    meta: PaginatedMeta


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = None


class ErrorDetail(BaseModel):
    """Single error entry within an error response."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""

    errors: list[ErrorDetail]
    meta: ResponseMeta
