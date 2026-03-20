"""Pydantic schemas for D7 Macroeconomic Data endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Macro Indicator ---

class MacroIndicatorResponse(BaseModel):
    indicator_id: uuid.UUID
    indicator_code: str
    name: str
    short_name: str | None = None
    description: str | None = None
    category: str
    subcategory: str | None = None
    country_code: str | None = None
    region: str | None = None
    frequency: str
    release_lag: int | None = None
    typical_release_day: str | None = None
    unit: str | None = None
    seasonal_adjustment: str | None = None
    source_agency: str | None = None
    source_url: str | None = None
    source_series_id: str | None = None
    base_period: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    has_yoy: bool = False
    has_mom: bool = False
    has_level: bool = False
    has_annualized: bool = False
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MacroIndicatorBriefResponse(BaseModel):
    indicator_id: uuid.UUID
    indicator_code: str
    name: str
    category: str
    country_code: str | None = None
    frequency: str
    unit: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


# --- Macro Value ---

class MacroValueResponse(BaseModel):
    indicator_id: uuid.UUID
    observation_date: date
    vintage_date: date
    value: float
    period_type: str | None = None
    revision_number: int = 0
    value_yoy: float | None = None
    value_yoy_percent: float | None = None
    value_mom: float | None = None
    value_mom_percent: float | None = None
    value_qoq_annualized: float | None = None
    is_preliminary: bool = False
    is_revised: bool = False
    previous_value: float | None = None
    consensus_estimate: float | None = None
    surprise: float | None = None
    surprise_percent: float | None = None
    release_date: date | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class MacroLatestValueResponse(BaseModel):
    indicator_code: str
    indicator_name: str
    observation_date: date
    value: float
    previous_value: float | None = None
    change: float | None = None
    change_percent: float | None = None
    unit: str | None = None
    frequency: str | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


# --- Macro Calendar ---

class MacroCalendarEntry(BaseModel):
    indicator_code: str
    indicator_name: str
    category: str
    country_code: str | None = None
    expected_release: date | None = None
    frequency: str | None = None
    previous_value: float | None = None
    consensus_estimate: float | None = None

    model_config = {"from_attributes": True}


# --- Central Bank Policy ---

class CentralBankPolicyResponse(BaseModel):
    policy_id: uuid.UUID
    bank_code: str
    meeting_date: date
    decision_date: date | None = None
    announcement_time: datetime | None = None
    policy_rate: float | None = None
    rate_change: float | None = None
    previous_rate: float | None = None
    rate_direction: str | None = None
    votes_for: int | None = None
    votes_against: int | None = None
    votes_abstain: int | None = None
    guidance_tone: str | None = None
    statement_summary: str | None = None
    statement_url: str | None = None
    minutes_url: str | None = None
    minutes_date: date | None = None
    next_meeting_date: date | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class CentralBankRateHistoryResponse(BaseModel):
    bank_code: str
    meetings: list[CentralBankPolicyResponse] = []
    current_rate: float | None = None
    last_change_date: date | None = None
    last_change_direction: str | None = None

    model_config = {"from_attributes": True}


# --- Bulk Request ---

class MacroBulkRequest(BaseModel):
    indicator_codes: list[str] = Field(..., max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    transformation: str | None = None


# --- Search ---

class MacroIndicatorSearchResponse(BaseModel):
    results: list[MacroIndicatorBriefResponse]
    total: int
    query: str
