"""Pydantic schemas for Pillar 3 Phase 4C: Intelligent Alerts & Earnings Intelligence."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class ConsolidatedAlertResponse(BaseModel):
    id: UUID
    entity_id: UUID
    alert_priority: int | None = None
    alert_categories: dict | None = None
    primary_headline: str | None = None
    primary_type: str | None = None
    source_alert_ids: dict | None = None
    secondary_alerts: dict | None = None
    ai_synthesis: str | None = None
    recommended_action: str | None = None
    related_catalysts: dict | None = None
    is_acknowledged: bool | None = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertFeedResponse(BaseModel):
    alerts: list[ConsolidatedAlertResponse]
    total_count: int
    critical_count: int


class EarningsSurpriseIntelResponse(BaseModel):
    id: UUID
    entity_id: UUID
    report_date: date
    fiscal_period: str | None = None
    eps_consensus: float | None = None
    eps_actual: float | None = None
    eps_surprise_pct: float | None = None
    revenue_consensus: float | None = None
    revenue_actual: float | None = None
    revenue_surprise_pct: float | None = None
    margin_analysis: dict | None = None
    guidance_implications: dict | None = None
    stock_reaction: dict | None = None
    ai_narrative: str | None = None
    key_takeaways: dict | None = None
    revision_implications: dict | None = None
    recommendation: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EarningsSurpriseListResponse(BaseModel):
    earnings: list[EarningsSurpriseIntelResponse]
    total_count: int
