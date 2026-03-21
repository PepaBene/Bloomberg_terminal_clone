"""Pydantic schemas for market movers."""

import uuid
from datetime import date

from pydantic import BaseModel


class MoverEntry(BaseModel):
    """Single entry in market movers."""
    rank: int
    security_id: uuid.UUID | None = None
    name: str | None = None
    ticker: str | None = None
    price: float | None = None
    change_pct: float | None = None
    volume: float | None = None


class MarketMoversResponse(BaseModel):
    """Market movers for a category."""
    snapshot_date: date
    category: str
    movers: list[MoverEntry] = []


class MarketMoversSummaryResponse(BaseModel):
    """Summary of market movers across categories."""
    snapshot_date: date
    gainers_count: int = 0
    losers_count: int = 0
    most_active_count: int = 0
