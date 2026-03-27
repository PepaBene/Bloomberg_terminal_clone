"""Pydantic schemas for Pillar 3 Insider Intelligence (Form 4 transactions, signals)."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class InsiderTransactionResponse(BaseModel):
    id: UUID
    entity_id: UUID
    reporting_person: str
    relationship: str
    transaction_type: str
    transaction_date: date
    shares: float | None = None
    price_per_share: float | None = None
    total_value: float | None = None
    is_open_market: bool
    is_10b5_1: bool
    filing_url: str | None = None

    model_config = {"from_attributes": True}


class InsiderSignalResponse(BaseModel):
    signal_type: str
    signal_strength: int
    signal_date: date | None = None
    detail: dict | None = None

    model_config = {"from_attributes": True}


class InsiderSummaryResponse(BaseModel):
    entity_id: UUID
    signals: list[InsiderSignalResponse] = []
    net_shares_30d: float | None = None
    net_value_30d: float | None = None
    net_shares_90d: float | None = None
    net_value_90d: float | None = None
    recent_transactions: list[InsiderTransactionResponse] = []


class InsiderScreenRequest(BaseModel):
    min_signal_strength: int | None = None
    signal_types: list[str] | None = None
    min_net_value_90d: float | None = None
    relationship_filter: list[str] | None = None


class InsiderScreenResponse(BaseModel):
    results: list[InsiderSummaryResponse] = []
    total_count: int = 0
