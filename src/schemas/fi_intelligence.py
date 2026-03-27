"""Pydantic schemas for Pillar 3 Phase 3C: FI Intelligence endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class YieldCurveBriefingResponse(BaseModel):
    id: UUID
    briefing_date: date
    spread_2s10s_bps: float | None = None
    spread_3m10y_bps: float | None = None
    curve_shape: str | None = None
    narrative: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class CreditMarketBriefingResponse(BaseModel):
    id: UUID
    briefing_date: date
    briefing_type: str | None = None
    ig_oas_bps: float | None = None
    hy_oas_bps: float | None = None
    ig_oas_1w_change: float | None = None
    hy_oas_1w_change: float | None = None
    credit_regime: str | None = None
    fallen_angels_this_period: dict | None = None
    rising_stars_this_period: dict | None = None
    narrative: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class IssuanceEventResponse(BaseModel):
    id: UUID
    entity_id: UUID | None = None
    issue_date: date
    coupon_rate: float | None = None
    maturity_date: date | None = None
    size_mm: float | None = None
    spread_at_issue_bps: float | None = None
    initial_talk_bps: float | None = None
    rating: str | None = None
    use_of_proceeds: str | None = None
    oversubscribed: bool = False
    source_url: str | None = None

    model_config = {"from_attributes": True}


class IssuanceWeekResponse(BaseModel):
    week_start: date
    week_end: date
    total_volume_mm: float
    ig_volume_mm: float
    hy_volume_mm: float
    deal_count: int
    avg_spread_bps: float | None = None


class IssuerCreditProfileResponse(BaseModel):
    entity_id: UUID
    legal_name: str | None = None
    current_rating: str | None = None
    credit_regime: str | None = None
    ig_oas_bps: float | None = None
    outstanding_bonds: int = 0
    total_debt_mm: float | None = None
    next_maturity_date: date | None = None
    rating_narrative: str | None = None
    debt_outlook: str | None = None


class CrossAssetSignalResponse(BaseModel):
    id: UUID
    entity_id: UUID
    signal_date: date
    signal_type: str | None = None
    equity_return_pct: float | None = None
    spread_change_bps: float | None = None
    severity: str | None = None
    narrative: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class FIDashboardResponse(BaseModel):
    briefing_date: date
    curve_shape: str | None = None
    credit_regime: str | None = None
    ig_oas_bps: float | None = None
    hy_oas_bps: float | None = None
    new_issues_today: int = 0
    active_signals: int = 0
