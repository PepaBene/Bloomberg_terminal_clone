"""Pydantic schemas for Pillar 4 Phase 1: Position endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class PositionAddRequest(BaseModel):
    ticker: str
    shares: Decimal
    cost_basis_per_share: Decimal
    acquisition_date: date | None = None
    notes: str | None = None


class PositionResponse(BaseModel):
    """Position response. Monetary / share fields are ``float`` on the
    wire (Pydantic v2 serializes ``Decimal`` as a string by default,
    which would break every existing JSON consumer)."""

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


class PositionUpdateRequest(BaseModel):
    shares: Decimal | None = None
    cost_basis_per_share: Decimal | None = None
    notes: str | None = None
