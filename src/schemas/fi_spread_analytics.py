"""Schemas for Pillar 2 FI Supplement Part 3: Spread Analytics."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SpreadAnalyticsResponse(BaseModel):
    cusip: str
    g_spread_bps: int | None = None
    z_spread_bps: int | None = None
    oas_bps: int | None = None
    spread_duration: float | None = None
    treasury_benchmark_maturity: float | None = None


class SpreadHistoryItem(BaseModel):
    price_date: date
    g_spread_bps: int | None = None
    z_spread_bps: int | None = None


class SpreadHistoryResponse(BaseModel):
    cusip: str
    history: list[SpreadHistoryItem]


class RelativeValueResponse(BaseModel):
    cusip: str
    current_spread_bps: float
    own_percentile: float
    own_z_score: float
    vs_peers_percentile: float | None = None
    vs_sector_diff_bps: int | None = None
    rich_cheap_score: float
    assessment: str  # RICH, FAIR, CHEAP


class BreakevenResponse(BaseModel):
    cusip: str
    spread_bps: float
    modified_duration: float
    carry_bps: float
    breakeven_widening_bps: float
    horizon_years: float


class SpreadScreenItem(BaseModel):
    cusip: str
    name: str | None = None
    g_spread_bps: int | None = None
    own_percentile: float | None = None
    rich_cheap_score: float | None = None


class SpreadScreenRequest(BaseModel):
    min_spread_bps: int | None = None
    max_spread_bps: int | None = None
    min_percentile: float | None = None
    max_percentile: float | None = None
    min_rich_cheap: float | None = None
    max_rich_cheap: float | None = None
    limit: int = 50


class SpreadScreenResponse(BaseModel):
    results: list[SpreadScreenItem]
    total: int
