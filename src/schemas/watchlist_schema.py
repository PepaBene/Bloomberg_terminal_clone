"""Pydantic schemas for Pillar 4 Phase 1: Watchlist endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class WatchlistCreateRequest(BaseModel):
    name: str
    description: str | None = None


class WatchlistEntityResponse(BaseModel):
    entity_id: UUID
    legal_name: str | None = None
    added_date: date | None = None


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    entities: list[WatchlistEntityResponse] = []


class WatchlistAlertItem(BaseModel):
    alert_type: str
    severity: str
    message: str
    entity_id: UUID | None = None
    triggered_at: datetime | None = None


class WatchlistAlertResponse(BaseModel):
    alerts: list[WatchlistAlertItem]


class WatchlistDashboardEntity(BaseModel):
    entity_id: UUID
    legal_name: str | None = None
    sector: str | None = None
    market_cap: float | None = None
    day_change_pct: float | None = None
    alert_count: int = 0


class WatchlistDashboardResponse(BaseModel):
    entities: list[WatchlistDashboardEntity]


class AlertConfigRequest(BaseModel):
    muted_types: list[str] | None = None
    min_severity: str | None = None


class EarningsCalendarEntry(BaseModel):
    entity_id: UUID
    legal_name: str | None = None
    report_date: date | None = None
    fiscal_quarter: str | None = None


class EarningsCalendarResponse(BaseModel):
    entries: list[EarningsCalendarEntry]


class AlertDigestResponse(BaseModel):
    total_alerts: int
    high_severity: int
    medium_severity: int
    low_severity: int
    summary: str | None = None
