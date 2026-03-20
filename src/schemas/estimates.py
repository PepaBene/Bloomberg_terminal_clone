"""Pydantic schemas for D4 Estimates endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ConsensusEstimateResponse(BaseModel):
    security_id: uuid.UUID
    metric: str
    period_end_date: date
    as_of_date: date
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: str | None = None
    currency: str | None = None
    mean: float | None = None
    median: float | None = None
    high: float | None = None
    low: float | None = None
    standard_deviation: float | None = None
    num_estimates: int | None = None
    num_revisions_up: int | None = None
    num_revisions_down: int | None = None

    model_config = {"from_attributes": True}


class EstimateSurpriseResponse(BaseModel):
    surprise_id: uuid.UUID
    security_id: uuid.UUID
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: str | None = None
    metric: str
    consensus_estimate: float | None = None
    actual_value: float | None = None
    surprise: float | None = None
    surprise_percent: float | None = None
    announcement_date: date | None = None

    model_config = {"from_attributes": True}


class CompanyGuidanceResponse(BaseModel):
    guidance_id: uuid.UUID
    entity_id: uuid.UUID
    security_id: uuid.UUID | None = None
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: str | None = None
    metric: str
    guidance_type: str | None = None
    point_estimate: float | None = None
    low_estimate: float | None = None
    high_estimate: float | None = None
    currency: str | None = None
    qualitative_guidance: str | None = None
    guidance_date: date | None = None
    source_event: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
