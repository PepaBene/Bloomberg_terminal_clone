"""Pydantic schemas for D6 Ownership endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- Institution Profile ---
class InstitutionProfileResponse(BaseModel):
    institution_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    cik: str | None = None
    institution_name: str
    institution_type: str | None = None
    tier: str | None = None
    aum: float | None = None
    number_of_holdings: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Institutional Holding ---
class InstitutionalHoldingResponse(BaseModel):
    institution_id: uuid.UUID
    security_id: uuid.UUID
    report_date: date
    filing_date: date | None = None
    shares_held: float | None = None
    market_value: float | None = None
    percent_of_portfolio: float | None = None
    percent_of_outstanding: float | None = None
    shares_change: float | None = None
    is_new_position: bool | None = None
    is_sold_out: bool | None = None
    source: str | None = None
    investment_discretion: str | None = None
    put_call: str | None = None
    voting_sole: float | None = None
    voting_shared: float | None = None
    voting_none: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Insider Holding ---
class InsiderHoldingResponse(BaseModel):
    transaction_id: uuid.UUID
    security_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    insider_name: str | None = None
    insider_title: str | None = None
    insider_relationship: str | None = None
    transaction_type: str | None = None
    transaction_date: date | None = None
    shares_transacted: float | None = None
    price_per_share: float | None = None
    total_value: float | None = None
    shares_owned_after: float | None = None
    ownership_nature: str | None = None

    model_config = {"from_attributes": True}


# --- Ownership Summary ---
class OwnershipSummaryResponse(BaseModel):
    security_id: uuid.UUID
    report_date: date
    institutional_holders_count: int | None = None
    institutional_shares: float | None = None
    insider_shares: float | None = None
    institutional_percent: float | None = None
    insider_percent: float | None = None
    top_10_concentration: float | None = None

    model_config = {"from_attributes": True}


# --- Short Interest ---
class ShortInterestResponse(BaseModel):
    security_id: uuid.UUID
    settlement_date: date
    shares_short: float | None = None
    short_percent_float: float | None = None
    short_percent_outstanding: float | None = None
    days_to_cover: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}
