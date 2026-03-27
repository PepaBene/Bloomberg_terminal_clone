"""Pydantic schemas for Pillar 4 Phase 1: Transaction endpoints."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class TransactionCreateRequest(BaseModel):
    ticker: str
    transaction_type: str
    transaction_date: date
    shares: Decimal
    price_per_share: Decimal
    commission: Decimal = Decimal("0")
    notes: str | None = None


class TransactionResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    security_id: UUID | None = None
    ticker: str | None = None
    transaction_type: str
    transaction_date: date
    settlement_date: date | None = None
    shares: float | None = None
    price_per_share: float | None = None
    gross_amount: float | None = None
    commission: float | None = None
    net_amount: float | None = None
    cash_impact: float | None = None
    source: str
    source_reference: str | None = None
    notes: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
