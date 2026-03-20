"""Pydantic schemas for D2 Security Master endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Security Identifier ---
class SecurityIdentifierResponse(BaseModel):
    identifier_type: str
    identifier_value: str
    source: str | None = None

    model_config = {"from_attributes": True}


# --- Equity Details ---
class EquityDetailsResponse(BaseModel):
    shares_outstanding: float | None = None
    shares_authorized: float | None = None
    float_shares: float | None = None
    par_value: float | None = None
    par_value_currency: str | None = None
    voting_rights: bool | None = None
    votes_per_share: float | None = None
    dividend_frequency: str | None = None
    dividend_currency: str | None = None
    share_class: str | None = None
    share_class_description: str | None = None
    conversion_ratio: float | None = None

    model_config = {"from_attributes": True}


# --- Fixed Income Details ---
class FixedIncomeDetailsResponse(BaseModel):
    face_value: float | None = None
    face_currency: str | None = None
    minimum_denomination: float | None = None
    coupon_rate: float | None = None
    coupon_type: str | None = None
    coupon_frequency: str | None = None
    day_count_convention: str | None = None
    spread: float | None = None
    reference_rate: str | None = None
    reset_frequency: str | None = None
    floor: float | None = None
    cap: float | None = None
    first_coupon_date: date | None = None
    last_coupon_date: date | None = None
    first_settlement_date: date | None = None
    seniority: str | None = None
    collateral_type: str | None = None
    callable: bool = False
    puttable: bool = False
    has_financial_covenants: bool = False
    has_negative_pledge: bool = False
    has_cross_default: bool = False
    rated: bool = False

    model_config = {"from_attributes": True}


# --- Credit Rating ---
class CreditRatingResponse(BaseModel):
    agency: str
    rating: str
    outlook: str | None = None
    rating_date: date | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


# --- Call/Put Schedule ---
class CallPutScheduleResponse(BaseModel):
    schedule_type: str
    effective_date: date
    price: float | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


# --- EOD Price ---
class EODPriceResponse(BaseModel):
    price_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    close_adjusted: float | None = None
    volume: int | None = None
    currency: str | None = None
    adjustment_factor: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


# --- Security (full) ---
class SecurityResponse(BaseModel):
    security_id: uuid.UUID
    security_type: str
    security_subtype: str | None = None
    issuer_entity_id: uuid.UUID | None = None
    name: str
    short_name: str | None = None
    description: str | None = None
    status: str
    status_date: date | None = None
    status_reason: str | None = None
    issue_date: date | None = None
    maturity_date: date | None = None
    issue_amount: float | None = None
    issue_currency: str | None = None
    asset_class: str
    cfi_code: str | None = None
    primary_exchange_mic: str | None = None
    primary_currency: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Expandable
    identifiers: list[SecurityIdentifierResponse] | None = None
    equity_details: EquityDetailsResponse | None = None
    fixed_income_details: FixedIncomeDetailsResponse | None = None
    credit_ratings: list[CreditRatingResponse] | None = None
    call_put_schedule: list[CallPutScheduleResponse] | None = None

    model_config = {"from_attributes": True}


# --- Security Brief (for lists) ---
class SecurityBriefResponse(BaseModel):
    security_id: uuid.UUID
    name: str
    short_name: str | None = None
    security_type: str
    asset_class: str
    status: str
    primary_exchange_mic: str | None = None

    model_config = {"from_attributes": True}


# --- Security Search ---
class SecuritySearchResult(BaseModel):
    security_id: uuid.UUID
    name: str
    short_name: str | None = None
    security_type: str
    asset_class: str
    status: str
    ticker: str | None = None
    exchange: str | None = None
    score: float = 0.0


class SecuritySearchResponse(BaseModel):
    results: list[SecuritySearchResult]
    total: int
    query: str


# --- Bulk Lookup ---
class SecurityIdentifierLookup(BaseModel):
    type: str
    value: str


class SecurityBulkLookupRequest(BaseModel):
    identifiers: list[SecurityIdentifierLookup]


class SecurityBulkLookupResponse(BaseModel):
    results: list[SecurityResponse | None]


# --- Translate ---
class TranslateRequest(BaseModel):
    source_type: str
    source_value: str
    target_types: list[str]


class TranslateResult(BaseModel):
    type: str
    value: str


class TranslateResponse(BaseModel):
    source_type: str
    source_value: str
    translations: list[TranslateResult]
