"""Pydantic schemas for D9 ESG & Sustainability endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ESGScoreResponse(BaseModel):
    score_id: uuid.UUID
    entity_id: uuid.UUID
    provider: str
    as_of_date: date
    esg_score: float | None = None
    esg_percentile: float | None = None
    esg_rating: str | None = None
    environmental_score: float | None = None
    social_score: float | None = None
    governance_score: float | None = None
    controversy_score: float | None = None
    controversy_level: str | None = None
    score_trend: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ESGMetricResponse(BaseModel):
    metric_id: uuid.UUID
    entity_id: uuid.UUID
    metric_type: str
    metric_category: str | None = None
    period_end_date: date | None = None
    period_type: str | None = None
    value: float | None = None
    unit: str | None = None
    is_reported: bool | None = None
    source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ESGControversyResponse(BaseModel):
    controversy_id: uuid.UUID
    entity_id: uuid.UUID
    controversy_type: str
    severity: str | None = None
    description: str | None = None
    start_date: date | None = None
    resolution_date: date | None = None
    status: str | None = None
    estimated_financial_impact: float | None = None
    source: str | None = None
    source_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ESGOverviewResponse(BaseModel):
    entity_id: uuid.UUID
    scores: list[ESGScoreResponse] = []
    metrics: list[ESGMetricResponse] = []
    controversies: list[ESGControversyResponse] = []

    model_config = {"from_attributes": True}
