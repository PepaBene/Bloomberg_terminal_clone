"""Pydantic schemas for D5 Corporate Actions endpoints."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


# --- Corporate Action (base) ---
class CorporateActionResponse(BaseModel):
    action_id: uuid.UUID
    action_type: str
    action_subtype: str | None = None
    security_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
    announcement_date: date | None = None
    ex_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    status: str
    description: str | None = None
    source: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Dividend Action ---
class DividendActionResponse(BaseModel):
    action_id: uuid.UUID
    dividend_type: str
    frequency: str | None = None
    gross_amount: float | None = None
    currency: str | None = None
    tax_rate: float | None = None
    qualified: bool | None = None
    stock_dividend_ratio: float | None = None

    model_config = {"from_attributes": True}


# --- Split Action ---
class SplitActionResponse(BaseModel):
    action_id: uuid.UUID
    split_ratio_from: int
    split_ratio_to: int
    split_factor: float | None = None
    adjustment_factor: float | None = None

    model_config = {"from_attributes": True}


# --- Merger & Acquisition Action ---
class MergerAcquisitionActionResponse(BaseModel):
    action_id: uuid.UUID
    transaction_type: str
    acquirer_entity_id: uuid.UUID | None = None
    target_entity_id: uuid.UUID | None = None
    deal_value: float | None = None
    deal_currency: str | None = None
    price_per_share: float | None = None
    cash_component: float | None = None
    stock_component: float | None = None
    consideration_type: str | None = None
    premium_1day: float | None = None
    premium_30day: float | None = None
    conditions: dict | None = None
    termination_fee: float | None = None

    model_config = {"from_attributes": True}
