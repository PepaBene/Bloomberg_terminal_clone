"""Pydantic schemas for Pillar 3 Alerts & Watchlist."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class AlertEventResponse(BaseModel):
    id: UUID
    alert_type: str
    priority: str
    entity_id: UUID
    title: str
    detail: dict | None = None
    is_acknowledged: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertRuleCreateRequest(BaseModel):
    alert_type: str
    entity_scope: dict | None = None
    conditions: dict | None = None
    priority_threshold: str | None = "LOW"
    delivery_preference: str = "DAILY_DIGEST"


class AlertRuleResponse(BaseModel):
    id: UUID
    alert_type: str
    entity_scope: dict | None = None
    conditions: dict | None = None
    priority_threshold: str | None = None
    delivery_preference: str
    is_active: bool

    model_config = {"from_attributes": True}


class WatchlistEntryResponse(BaseModel):
    entity_id: UUID
    added_date: date
    notes: str | None = None

    model_config = {"from_attributes": True}


class WatchlistAddRequest(BaseModel):
    entity_id: UUID
    notes: str | None = None
