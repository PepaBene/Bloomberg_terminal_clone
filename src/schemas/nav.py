"""Pydantic schemas for Pillar 4 Phase 1: NAV endpoints.

NAV / market-value fields use ``Decimal`` so a $1B+ portfolio doesn't
lose its cents on the float trip through JSON (P4-M-004). Returns and
ratios stay ``float`` because their precision is well within float range.
"""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class NAVResponse(BaseModel):
    nav: Decimal
    market_value: Decimal | None = None
    cash_balance: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    cash_weight: float | None = None
    position_count: int = 0


class NAVHistoryEntry(BaseModel):
    date: date
    nav: Decimal
    daily_return: float | None = None
    cumulative_return: float | None = None


class NAVHistoryResponse(BaseModel):
    history: list[NAVHistoryEntry]


class NAVSnapshotResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    snapshot_date: date
    nav: Decimal
    market_value: Decimal | None = None
    cash_balance: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    daily_return: float | None = None
    cumulative_return: float | None = None
    benchmark_daily_return: float | None = None
    benchmark_cumulative_return: float | None = None
    positions_snapshot: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
