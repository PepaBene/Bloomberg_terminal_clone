"""Pydantic schemas for Earnings Intelligence API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class EarningsSurpriseResponse(BaseModel):
    """Earnings surprise with market reaction."""
    surprise_id: uuid.UUID
    entity_id: uuid.UUID
    fiscal_year: int
    fiscal_quarter: int
    period_end_date: date | None = None
    actual_eps: float | None = None
    actual_revenue: float | None = None
    consensus_eps: float | None = None
    consensus_revenue: float | None = None
    eps_surprise: float | None = None
    eps_surprise_pct: float | None = None
    revenue_surprise: float | None = None
    revenue_surprise_pct: float | None = None
    announcement_date: date | None = None
    price_reaction_pct: float | None = None
    price_reaction_5d_pct: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GuidanceTrackingResponse(BaseModel):
    """Corporate guidance tracking."""
    guidance_id: uuid.UUID
    entity_id: uuid.UUID
    guidance_fiscal_year: int
    guidance_fiscal_quarter: int | None = None
    metric: str
    guidance_low: float | None = None
    guidance_high: float | None = None
    guidance_midpoint: float | None = None
    guidance_date: date
    guidance_type: str | None = None
    prior_guidance_low: float | None = None
    prior_guidance_high: float | None = None
    consensus_at_guidance_date: float | None = None
    guidance_vs_consensus: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
