"""Pydantic schemas for Money Market Rates API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class MoneyMarketRateResponse(BaseModel):
    """Daily money market rate."""
    id: uuid.UUID
    rate_date: date
    rate_type: str
    rate_value: float | None = None
    source: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
