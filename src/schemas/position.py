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
    """Position response. All monetary / share fields kept as ``Decimal``
    to preserve precision through serialization (P4-M-002) — share counts
    in particular use Numeric(20, 6) and lose digits via float."""

    id: UUID
    portfolio_id: UUID
    security_id: UUID | None = None
    ticker: str
    status: str
    shares: Decimal | None = None
    cost_basis_total: Decimal | None = None
    cost_basis_per_share: Decimal | None = None
    first_acquisition_date: date | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_pct: Decimal | None = None
    weight: Decimal | None = None
    closing_price: Decimal | None = None
    day_change_pct: Decimal | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PositionUpdateRequest(BaseModel):
    shares: Decimal | None = None
    cost_basis_per_share: Decimal | None = None
    notes: str | None = None
