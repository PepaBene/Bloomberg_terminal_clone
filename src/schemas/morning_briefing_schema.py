"""Pydantic schemas for Pillar 3 Phase 4A: Morning Briefings."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class MorningBriefingResponse(BaseModel):
    id: UUID
    user_id: UUID
    briefing_date: date
    regional_context: str | None = None
    executive_summary: str | None = None
    portfolio_impact: dict | None = None
    key_news: dict | None = None
    thesis_updates: dict | None = None
    macro_context: dict | None = None
    actionable_insights: dict | None = None
    delivery_format: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class BriefingPreferenceRequest(BaseModel):
    """user_id is no longer part of the request body -- it's derived from
    the authenticated caller (Depends(get_current_active_user))."""

    portfolio_entity_ids: dict | None = None
    watchlist_entity_ids: dict | None = None
    sector_focus: dict | None = None
    risk_tolerance: str | None = None
    delivery_time_utc: str | None = None
    delivery_format: str | None = None
    timezone: str | None = None
    is_active: bool = True


class BriefingPreferenceResponse(BaseModel):
    id: UUID
    user_id: UUID
    portfolio_entity_ids: dict | None = None
    watchlist_entity_ids: dict | None = None
    sector_focus: dict | None = None
    risk_tolerance: str | None = None
    delivery_time_utc: str | None = None
    delivery_format: str | None = None
    timezone: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}
