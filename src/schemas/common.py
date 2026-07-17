"""Common schemas: pagination, filtering, response envelope."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def round_or_none(value: float | None, ndigits: int) -> float | None:
    """Round a float for JSON serialization, passing ``None`` through.

    P4-M-001-007: financial response schemas deliberately keep monetary /
    share / ratio fields typed as plain ``float`` rather than ``Decimal`` --
    Pydantic v2 serializes ``Decimal`` as a quoted JSON *string* by default,
    which breaks every existing frontend ``Number(...)`` parse. Using
    ``float`` keeps the wire format a JSON number, but ``float`` also
    reintroduces binary floating-point noise (e.g. ``0.1 + 0.2`` artifacts)
    that isn't present in the underlying ``Numeric`` DB column. This helper
    is used from ``field_serializer`` hooks to round each field back down to
    the number of decimal places the field is actually meaningful at
    (mirroring the source column's declared ``Numeric(precision, scale)``),
    so the wire value doesn't imply false precision beyond what's stored.
    """
    return None if value is None else round(value, ndigits)


class FinancialBaseModel(BaseModel):
    """Base model for schemas with Decimal financial fields.

    Configures JSON serialization so Decimal values are emitted as floats,
    keeping downstream consumers (JS frontends, etc.) happy while preserving
    precision inside the Python layer.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: float(v)},
    )


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
