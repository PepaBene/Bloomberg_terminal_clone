"""Pydantic schemas for E6 Institutional Flow Analytics endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Institution-level responses
# ---------------------------------------------------------------------------

class InstitutionDetailResponse(BaseModel):
    """Full institution profile with derived analytics."""

    model_config = {"from_attributes": True}

    institution_id: uuid.UUID
    institution_name: str
    institution_type: str | None = None
    tier: str | None = None
    aum: float | None = None
    number_of_holdings: int | None = None
    investment_style: str | None = None
    concentration_score: float | None = None


class HoldingResponse(BaseModel):
    """Single holding for an institution or security."""

    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    security_id: uuid.UUID | None = None
    security_name: str | None = None
    report_date: date | None = None
    shares_held: float | None = None
    market_value: float | None = None
    percent_of_portfolio: float | None = None
    percent_of_outstanding: float | None = None


class HoldingChangeResponse(BaseModel):
    """Position change between quarters."""

    institution_id: uuid.UUID | None = None
    institution_name: str | None = None
    security_id: uuid.UUID | None = None
    security_name: str | None = None
    report_date: date | None = None
    prior_shares: float | None = None
    current_shares: float | None = None
    shares_change: float | None = None
    change_type: str | None = None  # NEW_POSITION, CLOSED_POSITION, INCREASED, DECREASED
    percent_change: float | None = None
    market_value: float | None = None


class InstitutionHistoryPoint(BaseModel):
    """Single quarter summary for an institution."""

    report_date: date
    total_positions: int | None = None
    total_value: float | None = None
    new_positions: int | None = None
    closed_positions: int | None = None


class InstitutionHistoryResponse(BaseModel):
    """Multi-quarter history for an institution."""

    institution_id: uuid.UUID
    institution_name: str | None = None
    data_points: list[InstitutionHistoryPoint] = []


# ---------------------------------------------------------------------------
# Security-level flow responses
# ---------------------------------------------------------------------------

class FlowSummaryResponse(BaseModel):
    """Aggregated institutional flow for a security."""

    security_id: uuid.UUID
    ticker: str | None = None
    report_date: date | None = None
    new_positions: int | None = None
    closed_positions: int | None = None
    increased_positions: int | None = None
    decreased_positions: int | None = None
    net_shares_change: float | None = None
    net_value_change: float | None = None
    buy_sell_ratio: float | None = None
    breadth_score: float | None = None
    conviction_score: float | None = None
    smart_money_flow: float | None = None
    flow_trend_3q: str | None = None
    flow_trend_4q: str | None = None
    squeeze_potential: str | None = None
    data_quality: str = "COMPLETE"


class SecurityHolderResponse(BaseModel):
    """Institution holding a security."""

    institution_id: uuid.UUID
    institution_name: str
    institution_type: str | None = None
    tier: str | None = None
    shares_held: float | None = None
    market_value: float | None = None
    percent_of_portfolio: float | None = None
    percent_of_outstanding: float | None = None
    shares_change: float | None = None
    change_type: str | None = None


class ShortInterestDetailResponse(BaseModel):
    """Short interest data for a security."""

    security_id: uuid.UUID
    settlement_date: date | None = None
    shares_short: float | None = None
    short_percent_float: float | None = None
    short_percent_outstanding: float | None = None
    days_to_cover: float | None = None
    squeeze_potential: str | None = None


class FlowHistoryPoint(BaseModel):
    """Single quarter of flow data."""

    report_date: date
    net_shares_change: float | None = None
    breadth_score: float | None = None
    smart_money_flow: float | None = None
    holders_count: int | None = None


class FlowHistoryResponse(BaseModel):
    """Multi-quarter flow history for a security."""

    security_id: uuid.UUID
    data_points: list[FlowHistoryPoint] = []


# ---------------------------------------------------------------------------
# Market-level aggregation responses
# ---------------------------------------------------------------------------

class MarketFlowResponse(BaseModel):
    """Market-wide institutional flow summary."""

    report_date: date | None = None
    total_new_positions: int | None = None
    total_closed_positions: int | None = None
    net_institutional_flow: float | None = None
    breadth_score: float | None = None


class SectorFlowResponse(BaseModel):
    """Institutional flow aggregated by sector."""

    gics_sector: str
    sector_name: str | None = None
    net_flow: float | None = None
    new_positions: int | None = None
    closed_positions: int | None = None


class SmartMoneyResponse(BaseModel):
    """Smart money (whale-tier) flow for a security."""

    security_id: uuid.UUID
    ticker: str | None = None
    name: str | None = None
    whale_net_shares: float | None = None
    whale_net_value: float | None = None
    smart_money_signal: str | None = None  # BULLISH, BEARISH, NEUTRAL


# ---------------------------------------------------------------------------
# Alert responses
# ---------------------------------------------------------------------------

class FlowAlertResponse(BaseModel):
    """Institutional flow alert."""

    model_config = {"from_attributes": True}

    alert_id: uuid.UUID
    alert_type: str
    security_id: uuid.UUID
    ticker: str | None = None
    institution_name: str | None = None
    headline: str
    report_date: date
    shares_involved: float | None = None
    value_involved: float | None = None
    percent_of_outstanding: float | None = None
    severity: str = "INFO"
