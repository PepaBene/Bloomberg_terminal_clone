"""Pydantic schemas for Pillar 4 Phase 1: NAV endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class NAVResponse(BaseModel):
    nav: float
    market_value: float | None = None
    cash_balance: float | None = None
    unrealized_pnl: float | None = None
    cash_weight: float | None = None
    position_count: int = 0


class NAVHistoryEntry(BaseModel):
    date: date
    nav: float
    daily_return: float | None = None
    cumulative_return: float | None = None


class NAVHistoryResponse(BaseModel):
    history: list[NAVHistoryEntry]


class NAVSnapshotResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    snapshot_date: date
    nav: float
    market_value: float | None = None
    cash_balance: float | None = None
    unrealized_pnl: float | None = None
    daily_return: float | None = None
    cumulative_return: float | None = None
    benchmark_daily_return: float | None = None
    benchmark_cumulative_return: float | None = None
    positions_snapshot: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
