"""Pydantic schemas for Pillar 4 Phase 1: Position endpoints."""

from pydantic import BaseModel, field_serializer
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from src.schemas.common import round_or_none


class PositionAddRequest(BaseModel):
    ticker: str
    shares: Decimal
    cost_basis_per_share: Decimal
    acquisition_date: date | None = None
    notes: str | None = None


class PositionResponse(BaseModel):
    """Position response.

    P4-M-002: monetary / share fields are deliberately kept as ``float``
    on the wire (Pydantic v2 serializes ``Decimal`` as a quoted string by
    default, which would break every existing JSON consumer). Each field
    is rounded via ``field_serializer`` to the decimal scale of its source
    ``Numeric`` DB column so the wire value doesn't imply false precision.
    """

    id: UUID
    portfolio_id: UUID
    security_id: UUID | None = None
    ticker: str
    status: str
    shares: float | None = None
    cost_basis_total: float | None = None
    cost_basis_per_share: float | None = None
    first_acquisition_date: date | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    weight: float | None = None
    closing_price: float | None = None
    day_change_pct: float | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    # shares: Numeric(20, 6); cost_basis_per_share: Numeric(15, 6)
    @field_serializer("shares", "cost_basis_per_share")
    def _round_6dp(self, v: float | None) -> float | None:
        return round_or_none(v, 6)

    # cost_basis_total / market_value / unrealized_pnl: Numeric(20, 2)
    @field_serializer("cost_basis_total", "market_value", "unrealized_pnl")
    def _round_money(self, v: float | None) -> float | None:
        return round_or_none(v, 2)

    # unrealized_pnl_pct: Numeric(10, 4); weight: Numeric(8, 4);
    # closing_price: Numeric(15, 4); day_change_pct: Numeric(10, 4)
    @field_serializer("unrealized_pnl_pct", "weight", "closing_price", "day_change_pct")
    def _round_4dp(self, v: float | None) -> float | None:
        return round_or_none(v, 4)


class PositionUpdateRequest(BaseModel):
    shares: Decimal | None = None
    cost_basis_per_share: Decimal | None = None
    notes: str | None = None
