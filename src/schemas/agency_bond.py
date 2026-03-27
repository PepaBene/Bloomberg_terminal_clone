"""Pydantic v2 schemas for Agency Bonds API (D11 FI Supplement P8)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AgencyBondResponse(BaseModel):
    """Full agency bond representation."""

    bond_id: uuid.UUID
    cusip: str
    issuer_name: str | None = None
    agency_type: str | None = None
    backing_type: str | None = None
    coupon_rate: float | None = None
    coupon_type: str | None = None
    coupon_frequency: int | None = None
    maturity_date: date
    issue_date: date | None = None
    original_amount_mm: float | None = None
    outstanding_amount_mm: float | None = None
    currency: str | None = None
    is_callable: bool = False
    first_call_date: date | None = None
    is_outstanding: bool = True
    status: str | None = None
    security_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgencyBondSummary(BaseModel):
    """Lightweight agency bond summary."""

    bond_id: uuid.UUID
    cusip: str
    issuer_name: str | None = None
    agency_type: str | None = None
    coupon_rate: float | None = None
    maturity_date: date
    is_outstanding: bool = True

    model_config = {"from_attributes": True}
