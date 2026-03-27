"""Pydantic schemas for Pillar 3 Phase 3C: Alert Expansion endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class FIAlertConfigResponse(BaseModel):
    id: UUID
    user_id: str
    alert_type: str
    is_enabled: bool = True
    threshold_value: float | None = None
    entity_scope: dict | None = None

    model_config = {"from_attributes": True}


class FIAlertConfigCreateRequest(BaseModel):
    user_id: str
    alert_type: str
    is_enabled: bool = True
    threshold_value: float | None = None
    entity_scope: dict | None = None


class QualityAlertResponse(BaseModel):
    entity_id: UUID
    entity_name: str | None = None
    alert_type: str
    severity: str
    current_score: float | None = None
    prior_score: float | None = None
    change: float | None = None
    triggered_at: datetime | None = None


class FlowAlertResponse(BaseModel):
    entity_id: UUID
    entity_name: str | None = None
    alert_type: str
    direction: str
    volume_mm: float | None = None
    z_score: float | None = None
    triggered_at: datetime | None = None


class FIRatingChangeResponse(BaseModel):
    entity_id: UUID | None = None
    entity_name: str | None = None
    agency: str | None = None
    old_rating: str | None = None
    new_rating: str | None = None
    direction: str | None = None
    event_date: date | None = None
    is_fallen_angel: bool = False
    is_rising_star: bool = False


class FallenAngelResponse(BaseModel):
    entity_id: UUID | None = None
    entity_name: str | None = None
    agency: str | None = None
    old_rating: str | None = None
    new_rating: str | None = None
    event_date: date | None = None
    spread_impact_bps: float | None = None


class SpreadMoveResponse(BaseModel):
    entity_id: UUID | None = None
    entity_name: str | None = None
    spread_bps: float | None = None
    spread_change_bps: float | None = None
    spread_change_pct: float | None = None
    as_of_date: date | None = None
    severity: str | None = None
