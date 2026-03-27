"""Pydantic v2 schemas for Bond Issuance API (D11 FI Supplement P7)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BondIssuanceResponse(BaseModel):
    """Full bond issuance representation."""

    issuance_id: uuid.UUID
    issuer_entity_id: uuid.UUID
    bond_id: uuid.UUID | None = None
    pricing_date: date | None = None
    settlement_date: date | None = None
    announcement_date: date | None = None
    coupon_rate: float | None = None
    maturity_date: date | None = None
    seniority: str | None = None
    issue_price: float | None = None
    issue_yield: float | None = None
    initial_talk_low_bps: int | None = None
    initial_talk_high_bps: int | None = None
    final_spread_bps: int | None = None
    tightening_bps: int | None = None
    announced_size_mm: float | None = None
    issued_size_mm: float | None = None
    lead_left_bookrunner: str | None = None
    all_bookrunners: list[str] | None = None
    use_of_proceeds: str | None = None
    currency: str | None = None
    is_benchmark: bool = False
    is_144a: bool = False
    is_registered: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class IssuanceVolumeResponse(BaseModel):
    """Aggregated issuance volume for a period."""

    period: str
    count: int
    total_volume_mm: float
    avg_size_mm: float

    model_config = {"from_attributes": True}


class LeagueTableEntry(BaseModel):
    """Bookrunner league table entry."""

    rank: int
    bookrunner: str
    deal_count: int
    total_volume_mm: float
    market_share_pct: float

    model_config = {"from_attributes": True}


class IssuanceScreenRequest(BaseModel):
    """Optional filters for issuance screening."""

    seniority: str | None = None
    currency: str | None = None
    min_size: float | None = None
    max_size: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    is_benchmark: bool | None = None
    is_144a: bool | None = None

    model_config = {"from_attributes": True}
