"""Pydantic v2 schemas for E9 Bond Pricing / FI Bond Analytics (Pillar 2 FI Supplement P1)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BondPriceResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    price_date: date
    clean_price: float
    dirty_price: float
    accrued_interest: float
    yield_to_maturity: float
    yield_to_worst: float | None = None


class CashFlowItem(BaseModel):
    model_config = {"from_attributes": True}

    date: date
    amount: float
    type: str  # COUPON, PRINCIPAL, CALL


class CashFlowScheduleResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    cash_flows: list[CashFlowItem]
    total_coupon_payments: float
    total_cash_flows: float


class PriceFromYieldRequest(BaseModel):
    coupon_rate: float
    face_value: float = 100.0
    settlement_date: date
    maturity_date: date
    yield_value: float
    frequency: int = 2
    day_count: str = "30/360"


class PriceFromYieldResponse(BaseModel):
    model_config = {"from_attributes": True}

    clean_price: float
    dirty_price: float
    accrued_interest: float
    yield_value: float


class YieldFromPriceRequest(BaseModel):
    coupon_rate: float
    face_value: float = 100.0
    settlement_date: date
    maturity_date: date
    clean_price: float
    frequency: int = 2
    day_count: str = "30/360"


class YieldFromPriceResponse(BaseModel):
    model_config = {"from_attributes": True}

    yield_to_maturity: float
    clean_price: float


class YTWRequest(BaseModel):
    coupon_rate: float
    face_value: float = 100.0
    settlement_date: date
    maturity_date: date
    clean_price: float
    frequency: int = 2
    day_count: str = "30/360"
    call_schedule: list[dict] | None = None


class YTWResponse(BaseModel):
    model_config = {"from_attributes": True}

    yield_to_worst: float
    yield_to: str  # MATURITY or CALL
    exercise_date: date | None = None
    yield_to_maturity: float
    call_yields: list[dict] | None = None


class BondPriceHistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    price_date: date
    clean_price: float | None = None
    dirty_price: float | None = None
    yield_to_maturity: float | None = None
    yield_to_worst: float | None = None


class BondPriceHistoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    cusip: str
    history: list[BondPriceHistoryItem]
