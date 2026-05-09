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
    """Transaction response. Monetary / share fields are ``Decimal`` so
    audit-grade dollar figures and 6-decimal share counts survive
    serialization without rounding (P4-M-003)."""

    id: UUID
    portfolio_id: UUID
    security_id: UUID | None = None
    ticker: str | None = None
    transaction_type: str
    transaction_date: date
    settlement_date: date | None = None
    shares: Decimal | None = None
    price_per_share: Decimal | None = None
    gross_amount: Decimal | None = None
    commission: Decimal | None = None
    net_amount: Decimal | None = None
    cash_impact: Decimal | None = None
    source: str
    source_reference: str | None = None
    notes: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
