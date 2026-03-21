"""Pydantic schemas for IPO Monitor API."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class IPOEventResponse(BaseModel):
    """Full IPO event record."""
    ipo_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    security_id: uuid.UUID | None = None
    s1_filing_date: date | None = None
    pricing_date: date | None = None
    trading_start_date: date | None = None
    initial_range_low: float | None = None
    initial_range_high: float | None = None
    offer_price: float | None = None
    shares_offered: float | None = None
    total_proceeds: float | None = None
    first_day_close: float | None = None
    first_day_return_pct: float | None = None
    current_price: float | None = None
    return_vs_offer_pct: float | None = None
    lead_underwriters: list[str] | None = None
    company_description: str | None = None
    gics_sector: str | None = None
    gics_industry: str | None = None
    revenue_ltm: float | None = None
    net_income_ltm: float | None = None
    status: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
