"""Pydantic schemas for Fund Holdings API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class FundResponse(BaseModel):
    """Investment fund summary."""
    fund_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    fund_name: str
    fund_ticker: str | None = None
    cik: str | None = None
    fund_type: str | None = None
    strategy: str | None = None
    category: str | None = None
    total_net_assets: float | None = None
    number_of_holdings: int | None = None
    top_10_concentration: float | None = None
    expense_ratio: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FundHoldingResponse(BaseModel):
    """Individual fund holding."""
    holding_id: uuid.UUID
    fund_id: uuid.UUID
    report_date: date
    security_id: uuid.UUID | None = None
    security_name: str | None = None
    cusip: str | None = None
    isin: str | None = None
    quantity: float | None = None
    market_value: float | None = None
    pct_of_nav: float | None = None
    asset_type: str | None = None
    issuer_category: str | None = None

    model_config = {"from_attributes": True}
