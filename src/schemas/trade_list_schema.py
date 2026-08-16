"""Pydantic schemas for Pillar 4 Phase 4: Trade list generation endpoint."""

from uuid import UUID

from pydantic import BaseModel


class TradeOrderEntry(BaseModel):
    ticker: str
    action: str
    shares: int
    notional_amount: float
    limit_price: float | None = None
    order_type: str
    time_in_force: str
    urgency: str
    notes: str = ""


class TradeListSummaryEntry(BaseModel):
    total_orders: int
    buy_count: int
    sell_count: int
    total_buy_notional: float
    total_sell_notional: float
    net_notional: float
    estimated_commission: float
    estimated_market_impact: float


class TradeListResponse(BaseModel):
    portfolio_id: UUID
    portfolio_name: str
    generated_at: str
    orders: list[TradeOrderEntry]
    summary: TradeListSummaryEntry
    metadata: dict
