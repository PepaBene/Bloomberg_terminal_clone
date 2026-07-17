"""Pydantic schemas for Pillar 4 Phase 1: Transaction endpoints."""

from pydantic import BaseModel, field_serializer
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from src.schemas.common import round_or_none


class TransactionCreateRequest(BaseModel):
    ticker: str
    transaction_type: str
    transaction_date: date
    shares: Decimal
    price_per_share: Decimal
    commission: Decimal = Decimal("0")
    notes: str | None = None


class TransactionResponse(BaseModel):
    """Transaction response.

    P4-M-003: monetary / share fields deliberately stay as ``float`` on
    the wire (Pydantic v2 serializes ``Decimal`` as a quoted string,
    which would break existing JSON number consumers). Each field is
    rounded via ``field_serializer`` to the decimal scale of its source
    ``Numeric`` DB column to avoid false floating-point precision.
    """

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

    # shares: Numeric(20, 6); price_per_share: Numeric(15, 6)
    @field_serializer("shares", "price_per_share")
    def _round_6dp(self, v: float | None) -> float | None:
        return round_or_none(v, 6)

    # gross_amount / commission / net_amount / cash_impact: Numeric(*, 2)
    @field_serializer("gross_amount", "commission", "net_amount", "cash_impact")
    def _round_money(self, v: float | None) -> float | None:
        return round_or_none(v, 2)


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
