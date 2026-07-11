"""Pydantic schemas for M&A Deal Database API."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class MandADealResponse(BaseModel):
    """Full M&A deal record."""
    deal_id: uuid.UUID
    acquirer_entity_id: uuid.UUID | None = None
    target_entity_id: uuid.UUID | None = None
    acquirer_name: str | None = None
    target_name: str | None = None
    deal_type: str | None = None
    deal_status: str | None = None
    is_hostile: bool = False
    total_value: float | None = None
    equity_value: float | None = None
    price_per_share: float | None = None
    premium_to_undisturbed: float | None = None
    payment_type: str | None = None
    cash_component: float | None = None
    stock_exchange_ratio: float | None = None
    ev_to_revenue: float | None = None
    ev_to_ebitda: float | None = None
    pe_ratio: float | None = None
    target_revenue_ltm: float | None = None
    target_ebitda_ltm: float | None = None
    target_net_income_ltm: float | None = None
    announcement_date: date | None = None
    completion_date: date | None = None
    termination_date: date | None = None
    expected_completion: date | None = None
    acquirer_financial_advisors: list[str] | None = None
    target_financial_advisors: list[str] | None = None
    # P1-M-026: acquirer_legal_counsel/target_legal_counsel and
    # regulatory_approvals_required were unvalidated JSONB and not exposed
    # in the output schema at all. They follow the same list-of-names
    # convention already established for *_financial_advisors.
    acquirer_legal_counsel: list[str] | None = None
    target_legal_counsel: list[str] | None = None
    regulatory_approvals_required: list[str] | None = None
    regulatory_status: str | None = None
    target_gics_sector: str | None = None
    target_gics_industry: str | None = None
    # P1-M-026: source_filings is a list of SEC accession-number strings,
    # same convention/producer pattern as ipo.py's source_filings field.
    source_filings: list[str] | None = None
    primary_source: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DealStatisticsResponse(BaseModel):
    """Aggregate deal statistics."""
    total_deals: int = 0
    total_value: float | None = None
    avg_premium: float | None = None
    avg_ev_to_ebitda: float | None = None
