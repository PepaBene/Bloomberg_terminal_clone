"""Pydantic v2 schemas for Corporate Bond API (D11 FI Supplement P4)."""

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field


class BondCallScheduleResponse(BaseModel):
    """Call schedule entry for a corporate bond."""

    id: uuid.UUID
    bond_id: uuid.UUID
    call_date: date
    call_price: float | None = None
    call_type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CorporateBondResponse(BaseModel):
    """Full corporate bond representation."""

    bond_id: uuid.UUID
    cusip: str
    isin: str | None = None
    figi: str | None = None
    issuer_entity_id: uuid.UUID
    issuer_name: str | None = None
    issuer_cik: str | None = None
    security_id: uuid.UUID | None = None
    name: str
    coupon_rate: float | None = None
    coupon_type: str | None = None
    coupon_frequency: int | None = None
    day_count_convention: str | None = None
    floating_reference_rate: str | None = None
    floating_spread_bps: int | None = None
    issue_date: date | None = None
    maturity_date: date
    first_coupon_date: date | None = None
    original_issue_amount: float | None = None
    outstanding_amount: float | None = None
    minimum_denomination: float | None = None
    currency: str | None = None
    seniority: str | None = None
    collateral_type: str | None = None
    is_guaranteed: bool = False
    guarantor_entity_id: uuid.UUID | None = None
    is_callable: bool = False
    callable_from_date: date | None = None
    call_type: str | None = None
    is_puttable: bool = False
    is_convertible: bool = False
    conversion_price: float | None = None
    initial_rating_sp: str | None = None
    initial_rating_moodys: str | None = None
    initial_rating_fitch: str | None = None
    is_investment_grade: bool | None = None
    use_of_proceeds: str | None = None
    use_of_proceeds_text: str | None = None
    has_change_of_control_put: bool = False
    has_negative_pledge: bool = False
    has_leverage_covenant: bool = False
    has_interest_coverage_covenant: bool = False
    source_filing_accession: str | None = None
    source_filing_type: str | None = None
    source_filing_date: date | None = None
    status: str = "OUTSTANDING"
    status_date: date | None = None
    status_reason: str | None = None
    call_schedule: list[BondCallScheduleResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BondTradeResponse(BaseModel):
    """TRACE trade response."""

    trade_id: uuid.UUID
    bond_id: uuid.UUID
    trade_date: date
    trade_time: time | None = None
    settlement_date: date | None = None
    price: float | None = None
    yield_value: float | None = None
    quantity: float | None = None
    quantity_reported: str | None = None
    trade_type: str | None = None
    is_when_issued: bool = False
    source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BondEODPriceResponse(BaseModel):
    """End-of-day bond price response."""

    id: uuid.UUID
    bond_id: uuid.UUID
    price_date: date
    last_trade_price: float | None = None
    vwap: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    trade_count: int | None = None
    total_volume: float | None = None
    yield_to_maturity: float | None = None
    yield_to_worst: float | None = None
    g_spread_bps: int | None = None
    treasury_benchmark_cusip: str | None = None
    liquidity_score: int | None = None
    has_sufficient_trades: bool = False
    price_source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BondAnalyticsResponse(BaseModel):
    """Computed analytics for a bond."""

    cusip: str
    price: float
    ytm: float
    ytw: float
    modified_duration: float
    macaulay_duration: float
    convexity: float
    g_spread_bps: int | None = None
    years_to_maturity: float


class BondScreenRequest(BaseModel):
    """Request body for bond screening."""

    seniority: str | None = None
    coupon_type: str | None = None
    min_coupon: float | None = None
    max_coupon: float | None = None
    min_maturity: date | None = None
    max_maturity: date | None = None
    currency: str | None = None
    is_callable: bool | None = None
    is_convertible: bool | None = None
    is_investment_grade: bool | None = None
    status: str | None = None
    min_outstanding: float | None = None
    max_outstanding: float | None = None
