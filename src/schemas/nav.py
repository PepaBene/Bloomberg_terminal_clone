"""Pydantic schemas for Pillar 4 Phase 1: NAV endpoints."""

from pydantic import BaseModel, field_serializer
from uuid import UUID
from datetime import date, datetime

from src.schemas.common import round_or_none

# P4-M-004: NAV/return fields are deliberately kept as ``float`` on the
# wire (Pydantic v2 serializes ``Decimal`` as a quoted string by default,
# which would break existing JSON number consumers). Each schema below
# rounds its fields via ``field_serializer`` to the decimal scale of the
# source ``Numeric`` DB column (NAV/cash amounts: 2dp, matching
# ``Numeric(20, 2)``; fractional returns/weights: 6dp, matching the
# ``Numeric(12, 8)`` return columns' meaningful precision) to avoid false
# floating-point precision on the wire.


class NAVResponse(BaseModel):
    nav: float
    market_value: float | None = None
    cash_balance: float | None = None
    unrealized_pnl: float | None = None
    cash_weight: float | None = None
    position_count: int = 0

    @field_serializer("nav", "market_value", "cash_balance", "unrealized_pnl")
    def _round_money(self, v: float | None) -> float | None:
        return round_or_none(v, 2)

    @field_serializer("cash_weight")
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class NAVHistoryEntry(BaseModel):
    date: date
    nav: float
    daily_return: float | None = None
    cumulative_return: float | None = None

    @field_serializer("nav")
    def _round_money(self, v: float) -> float:
        return round(v, 2)

    @field_serializer("daily_return", "cumulative_return")
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)


class NAVHistoryResponse(BaseModel):
    history: list[NAVHistoryEntry]


class NAVSnapshotResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    snapshot_date: date
    nav: float
    market_value: float | None = None
    cash_balance: float | None = None
    unrealized_pnl: float | None = None
    daily_return: float | None = None
    cumulative_return: float | None = None
    benchmark_daily_return: float | None = None
    benchmark_cumulative_return: float | None = None
    positions_snapshot: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("nav")
    def _round_money(self, v: float) -> float:
        return round(v, 2)

    @field_serializer("market_value", "cash_balance", "unrealized_pnl")
    def _round_money_optional(self, v: float | None) -> float | None:
        return round_or_none(v, 2)

    @field_serializer(
        "daily_return", "cumulative_return",
        "benchmark_daily_return", "benchmark_cumulative_return",
    )
    def _round_ratio(self, v: float | None) -> float | None:
        return round_or_none(v, 6)
