"""Pydantic schemas for Pillar 4 Phase 1: Portfolio Management endpoints."""

from pydantic import BaseModel, field_serializer
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from src.schemas.common import round_or_none


class PortfolioCreateRequest(BaseModel):
    portfolio_name: str
    portfolio_type: str = "REAL"
    benchmark_id: str | None = None
    inception_date: date
    initial_cash: Decimal
    tags: dict | None = None
    notes: str | None = None


class PortfolioResponse(BaseModel):
    """Portfolio response.

    P4-M-001: monetary fields are deliberately kept as ``float`` (not
    ``Decimal``) on the wire so JSON consumers get plain numbers --
    Pydantic v2 serializes ``Decimal`` as a quoted string by default, which
    would break every existing frontend ``Number(...)`` parse. To avoid
    reintroducing binary floating-point display noise, monetary fields are
    rounded to 2 decimal places (matching the ``Numeric(20, 2)`` DB columns)
    via ``field_serializer`` at the response boundary. Precision-sensitive
    callers should read the underlying ORM model directly.
    """

    id: UUID
    user_id: str
    portfolio_name: str
    portfolio_type: str
    benchmark_id: str | None = None
    inception_date: date
    base_currency: str
    initial_cash: float
    current_cash: float
    status: str
    tags: dict | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("initial_cash", "current_cash")
    def _round_money(self, v: float | None) -> float | None:
        return round_or_none(v, 2)


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioResponse]


class PortfolioUpdateRequest(BaseModel):
    portfolio_name: str | None = None
    benchmark_id: str | None = None
    status: str | None = None
    tags: dict | None = None
    notes: str | None = None
