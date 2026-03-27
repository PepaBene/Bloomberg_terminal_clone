"""Pydantic schemas for Pillar 3 Phase 4A: Company Primers."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class CompanyPrimerResponse(BaseModel):
    id: UUID
    entity_id: UUID
    primer_version: int
    generated_at: datetime | None = None
    executive_summary: str | None = None
    business_model: dict | None = None
    competitive_landscape: dict | None = None
    financial_health: dict | None = None
    strategic_initiatives: dict | None = None
    risk_factors: dict | None = None
    analyst_consensus: dict | None = None
    recent_catalysts: dict | None = None
    data_completeness_score: float | None = None
    last_filing_date: date | None = None
    last_earnings_call_date: date | None = None
    ai_enabled: bool = False
    prompt_template_used: str | None = None

    model_config = {"from_attributes": True}


class PrimerRefreshResponse(BaseModel):
    id: UUID
    entity_id: UUID
    refresh_type: str
    trigger_event: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PrimerListResponse(BaseModel):
    entity_id: UUID
    primer_version: int
    generated_at: datetime | None = None
    executive_summary: str | None = None
    data_completeness_score: float | None = None

    model_config = {"from_attributes": True}


class PrimerCompletenessResponse(BaseModel):
    entity_id: UUID
    data_completeness_score: float | None = None
    last_filing_date: date | None = None
    last_earnings_call_date: date | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}
