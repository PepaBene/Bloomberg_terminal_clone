"""Pydantic schemas for Pillar 3 Phase 3B Global Macro endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class CentralBankResponse(BaseModel):
    id: UUID
    bank_code: str
    bank_name: str | None = None
    country_code: str | None = None
    current_rate: float | None = None
    policy_stance: str | None = None
    next_meeting_date: date | None = None
    forward_guidance_summary: str | None = None

    model_config = {"from_attributes": True}


class CentralBankDecisionResponse(BaseModel):
    id: UUID
    bank_code: str
    decision_date: date
    rate_before: float | None = None
    rate_after: float | None = None
    rate_change_bps: int | None = None
    decision_type: str | None = None
    was_surprise: bool = False
    vote_split: str | None = None
    statement_summary: str | None = None

    model_config = {"from_attributes": True}


class GlobalMacroDashboardResponse(BaseModel):
    country_code: str
    indicator_type: str | None = None
    period_label: str | None = None
    value: float | None = None
    prior_value: float | None = None
    forecast_value: float | None = None
    source: str | None = None
    release_date: date | None = None

    model_config = {"from_attributes": True}


class InflationComparisonResponse(BaseModel):
    country_code: str
    value: float | None = None
    prior_value: float | None = None
    period_label: str | None = None
    release_date: date | None = None

    model_config = {"from_attributes": True}


class RecessionProbabilityResponse(BaseModel):
    country_code: str
    indicator_type: str | None = None
    value: float | None = None
    period_label: str | None = None
    release_date: date | None = None

    model_config = {"from_attributes": True}
