"""Pydantic schemas for Capital Structure API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DebtTrancheResponse(BaseModel):
    """Individual debt tranche within a capital structure."""
    tranche_id: uuid.UUID
    entity_id: uuid.UUID
    capital_structure_id: uuid.UUID
    instrument_name: str | None = None
    instrument_type: str | None = None
    principal_amount: float | None = None
    original_amount: float | None = None
    currency: str | None = None
    coupon_rate: float | None = None
    coupon_type: str | None = None
    floating_reference: str | None = None
    floating_spread: float | None = None
    issue_date: date | None = None
    maturity_date: date | None = None
    first_call_date: date | None = None
    next_put_date: date | None = None
    seniority_rank: int | None = None
    seniority_type: str | None = None
    collateral_description: str | None = None
    has_financial_covenants: bool = False
    has_change_of_control: bool = False
    has_cross_default: bool = False
    security_id: uuid.UUID | None = None
    extracted_from: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CapitalStructureResponse(BaseModel):
    """Full capital structure with tranches."""
    capital_structure_id: uuid.UUID
    entity_id: uuid.UUID
    as_of_date: date
    total_debt: float | None = None
    total_long_term_debt: float | None = None
    total_short_term_debt: float | None = None
    total_preferred_stock: float | None = None
    net_debt: float | None = None
    total_capitalization: float | None = None
    debt_to_capitalization: float | None = None
    source: str | None = None
    extraction_method: str | None = None
    confidence_score: float | None = None
    tranches: list[DebtTrancheResponse] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CapitalStructureSummaryResponse(BaseModel):
    """Aggregate metrics only (no tranches)."""
    entity_id: uuid.UUID
    as_of_date: date
    total_debt: float | None = None
    net_debt: float | None = None
    total_capitalization: float | None = None
    debt_to_capitalization: float | None = None
    total_long_term_debt: float | None = None
    total_short_term_debt: float | None = None
    total_preferred_stock: float | None = None

    model_config = {"from_attributes": True}
