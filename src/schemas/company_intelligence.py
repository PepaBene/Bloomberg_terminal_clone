"""Pydantic schemas for company intelligence and primers."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class KeySignal(BaseModel):
    """A single key intelligence signal."""
    signal: str
    severity: str = "MEDIUM"
    detail: str | None = None


class ValuationContext(BaseModel):
    """Valuation context metrics."""
    pe_current: float | None = None
    pe_5y_avg: float | None = None
    pe_vs_peers: float | None = None
    ev_ebitda: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None


class CompanyBriefingResponse(BaseModel):
    """Response for a company intelligence briefing."""
    briefing_id: uuid.UUID
    entity_id: uuid.UUID
    briefing_type: str
    briefing_date: date
    status: str
    summary_text: str | None = None
    key_signals: list[KeySignal] = []
    valuation_context: ValuationContext | None = None
    value_investing_lens: dict | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class CompanyPrimerResponse(BaseModel):
    """Response for a company primer."""
    primer_id: uuid.UUID
    entity_id: uuid.UUID
    generated_date: date
    business_description: str | None = None
    segments_breakdown: dict | None = None
    competitive_position: str | None = None
    financial_summary: dict | None = None
    valuation_summary: dict | None = None
    ownership_summary: dict | None = None
    key_risks: list[str] | None = None
    recent_developments: list[dict] | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class SignalsOnlyResponse(BaseModel):
    """Signals-only response (no AI needed)."""
    entity_id: uuid.UUID
    signals: list[KeySignal] = []
    generated_at: datetime | None = None


class FinancialSummaryResponse(BaseModel):
    """Financial summary only (no AI needed)."""
    entity_id: uuid.UUID
    financial_summary: dict | None = None
    valuation_summary: dict | None = None
    generated_at: datetime | None = None
