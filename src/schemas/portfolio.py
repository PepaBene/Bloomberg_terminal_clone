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


class SectorAllocationEntry(BaseModel):
    sector: str
    weight: float
    count: int
    market_value: float


class TopHoldingEntry(BaseModel):
    ticker: str
    weight: float
    market_value: float


class ConcentrationSummary(BaseModel):
    hhi: float
    classification: str
    effective_positions: float


class PortfolioAnalyticsResponse(BaseModel):
    """Portfolio-level summary/allocation/concentration/PnL/cash snapshot.

    Computed at request time from live positions (portfolio_analytics.py),
    the same "no persisted snapshot needed" pattern as the risk dashboard
    (GET .../risk) -- there is nothing here that benefits from being
    stored, since it's a pure function of current holdings.
    """

    portfolio_id: UUID
    total_positions: int
    market_value: float
    cash_pct: float
    invested_pct: float
    avg_position_size: float
    sector_allocation: list[SectorAllocationEntry]
    top_holdings: list[TopHoldingEntry]
    concentration: ConcentrationSummary
    winners_count: int
    losers_count: int
    total_gain: float
    total_loss: float
    net_pnl: float
    win_rate: float
    cash_utilization_status: str
    cash_utilization_message: str
    portfolio_age_days: int
    portfolio_age_years: float
