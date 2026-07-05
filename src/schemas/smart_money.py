"""Pydantic schemas for Smart-Money / Notable-Filer tracking endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


# ── Registry ────────────────────────────────────────────────────────────

class NotableInvestorResponse(BaseModel):
    key: str
    display_name: str
    category: str  # GURU_13F / INSIDER_FORM4 / POLITICIAN
    vehicle: str | None = None
    role: str | None = None
    chamber: str | None = None
    party: str | None = None
    state: str | None = None
    tags: list[str] = []
    notes: str | None = None


# ── Positions / holdings ────────────────────────────────────────────────

class HoldingItem(BaseModel):
    ticker: str | None = None
    name: str | None = None
    market_value: float | None = None
    percent_of_portfolio: float | None = None
    shares: float | None = None
    conviction: float | None = None
    is_new_position: bool | None = None
    shares_change_pct: float | None = None


class FilerProfileResponse(BaseModel):
    display_name: str
    category: str
    num_holdings: int
    total_value: float
    top5_concentration_pct: float
    turnover: float
    new_positions: list[HoldingItem] = []
    exited_positions: list[HoldingItem] = []
    increased_positions: list[HoldingItem] = []
    decreased_positions: list[HoldingItem] = []
    top_holdings: list[HoldingItem] = []


# ── Congressional trades ────────────────────────────────────────────────

class CongressionalTradeResponse(BaseModel):
    id: uuid.UUID
    politician_name: str
    chamber: str | None = None
    party: str | None = None
    state: str | None = None
    ticker: str | None = None
    asset_description: str | None = None
    asset_type: str | None = None
    transaction_type: str
    transaction_date: date
    disclosure_date: date | None = None
    amount_range_low: float | None = None
    amount_range_high: float | None = None
    midpoint_amount: float | None = None
    size_bucket: str | None = None
    owner: str | None = None
    disclosure_lag_days: int | None = None
    is_late_disclosure: bool | None = None
    committee_conflict: bool | None = None
    conflict_committee: str | None = None
    source_url: str | None = None

    model_config = {"from_attributes": True}


# ── Signals / consensus ─────────────────────────────────────────────────

class FollowSignalResponse(BaseModel):
    display_name: str | None = None
    ticker: str | None = None
    category: str | None = None
    action: str | None = None
    direction: str
    strength: float
    rationale: str


class ConsensusRow(BaseModel):
    ticker: str
    buyers: list[str] = []
    sellers: list[str] = []
    net_score: int
    participants: int
    signal: str


class SmartMoneyFlowRow(BaseModel):
    ticker: str
    bullish: float
    bearish: float
    net_pressure: float
    events: int
    names: list[str] = []
    signal: str
