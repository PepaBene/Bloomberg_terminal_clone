"""Pydantic v2 schemas for Treasury Securities API (D11 FI Supplement P2)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TreasurySecurityResponse(BaseModel):
    """Full treasury security representation."""

    treasury_id: uuid.UUID
    cusip: str
    treasury_type: str
    coupon_rate: float | None = None
    coupon_frequency: int | None = None
    issue_date: date | None = None
    maturity_date: date
    original_issue_amount: float | None = None
    outstanding_amount: float | None = None
    auction_date: date | None = None
    auction_high_yield: float | None = None
    auction_price: float | None = None
    auction_bid_to_cover: float | None = None
    auction_median_yield: float | None = None
    auction_low_yield: float | None = None
    is_inflation_indexed: bool = False
    index_ratio: float | None = None
    ref_cpi_date: date | None = None
    ref_cpi_value: float | None = None
    is_stripped: bool = False
    stripped_from_cusip: str | None = None
    strip_type: str | None = None
    is_outstanding: bool = True
    status: str | None = None
    security_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TreasuryAuctionResponse(BaseModel):
    """Auction-specific subset of treasury security data."""

    cusip: str
    treasury_type: str
    auction_date: date | None = None
    auction_high_yield: float | None = None
    auction_price: float | None = None
    auction_bid_to_cover: float | None = None
    auction_median_yield: float | None = None
    auction_low_yield: float | None = None
    maturity_date: date
    issue_date: date | None = None
    coupon_rate: float | None = None

    model_config = {"from_attributes": True}


class TreasuryOnTheRunResponse(BaseModel):
    """On-the-run treasury: tenor bucket, CUSIP, and yield-to-maturity."""

    tenor: str
    cusip: str
    ytm: float | None = None

    model_config = {"from_attributes": True}
