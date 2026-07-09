"""Pydantic schemas for E10 Duration & Convexity Analytics."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class DurationResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    macaulay_duration: float
    modified_duration: float
    dv01: float
    convexity: float
    effective_duration: float | None = None
    effective_convexity: float | None = None
    key_rate_durations: dict[str, float] | None = None


class DurationHistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    price_date: date
    modified_duration: float
    dv01: float


class DurationHistoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    history: list[DurationHistoryItem]


class PortfolioPosition(BaseModel):
    cusip: str | None = None
    weight: float
    modified_duration: float
    dv01: float
    convexity: float = 0.0
    key_rate_durations: dict[str, float] | None = None


class PortfolioDurationRequest(BaseModel):
    positions: list[PortfolioPosition]


class PortfolioDurationResponse(BaseModel):
    weighted_avg_duration: float
    portfolio_dv01: float
    weighted_avg_convexity: float
    portfolio_key_rate_durations: dict[str, float] | None = None
    position_count: int


class KeyRateDurationResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    curve_date: date | None = None
    key_rate_durations: dict[str, float]
    total_key_rate_duration: float


class RateSensitivityItem(BaseModel):
    shift_bps: int
    price_change_pct: float
    estimated_new_price: float


class RateSensitivityResponse(BaseModel):
    cusip: str
    base_price: float
    modified_duration: float
    convexity: float
    sensitivity: list[RateSensitivityItem]
