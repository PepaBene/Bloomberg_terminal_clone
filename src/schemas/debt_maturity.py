"""Pydantic schemas for Debt Maturity Profile API."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class MaturityBucketResponse(BaseModel):
    """Single-year maturity bucket."""
    bucket_id: uuid.UUID
    year: int
    total_amount: float | None = None
    breakdown: list[dict[str, Any]] | None = None

    model_config = {"from_attributes": True}


class DebtMaturityResponse(BaseModel):
    """Full debt maturity profile with annual buckets."""
    profile_id: uuid.UUID
    entity_id: uuid.UUID
    as_of_date: date
    debt_maturing_1yr: float | None = None
    debt_maturing_2yr: float | None = None
    debt_maturing_3yr: float | None = None
    pct_debt_maturing_1yr: float | None = None
    pct_debt_maturing_3yr: float | None = None
    weighted_avg_maturity_years: float | None = None
    weighted_avg_coupon: float | None = None
    cash_to_1yr_maturities: float | None = None
    fcf_to_1yr_maturities: float | None = None
    maturity_wall_alert: bool = False
    near_term_stress: bool = False
    buckets: list[MaturityBucketResponse] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DebtMaturityMetricsResponse(BaseModel):
    """Derived maturity risk metrics."""
    entity_id: uuid.UUID
    as_of_date: date
    debt_maturing_1yr: float | None = None
    debt_maturing_2yr: float | None = None
    debt_maturing_3yr: float | None = None
    pct_debt_maturing_1yr: float | None = None
    pct_debt_maturing_3yr: float | None = None
    weighted_avg_maturity_years: float | None = None
    weighted_avg_coupon: float | None = None
    cash_to_1yr_maturities: float | None = None
    fcf_to_1yr_maturities: float | None = None
    maturity_wall_alert: bool = False
    near_term_stress: bool = False

    model_config = {"from_attributes": True}


class DebtMaturityAlertResponse(BaseModel):
    """Refinancing risk alert for an entity."""
    entity_id: uuid.UUID
    as_of_date: date
    maturity_wall_alert: bool
    near_term_stress: bool
    pct_debt_maturing_1yr: float | None = None
    debt_maturing_1yr: float | None = None
    cash_to_1yr_maturities: float | None = None

    model_config = {"from_attributes": True}
