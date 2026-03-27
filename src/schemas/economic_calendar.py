"""Pydantic schemas for Pillar 3 Phase 2: Economic Calendar."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class EconomicReleaseResponse(BaseModel):
    id: UUID
    release_type: str
    release_category: str
    release_date: date
    importance: str | None = None
    consensus_value: float | None = None
    prior_value: float | None = None
    actual_value: float | None = None
    surprise_value: float | None = None
    surprise_magnitude: float | None = None
    sector_sensitivity: dict | None = None
    ai_summary: str | None = None

    model_config = {"from_attributes": True}


class EconomicCalendarListResponse(BaseModel):
    releases: list[EconomicReleaseResponse] = []
    total_count: int = 0
