"""Benchmark / index model (Pillar 2 Frontend Bugs 93-95).

``GET /v1/benchmarks`` and ``POST /v1/benchmarks`` were declared in
``frontend/src/api/endpoints.ts`` and consumed by ``CustomIndexBuilder.tsx``
/ the quant benchmark hooks, but had no backing model or router anywhere in
``src/`` -- a permanent 404, not a wiring bug.

This model backs two kinds of row:

* Standard market indices (S&P 500, NASDAQ 100, Russell 1000/2000, Dow),
  tracked via the same tradeable-ETF-proxy idea already used by
  ``scripts/run_backtest_worker.py``'s ``_BENCHMARK_TICKER_MAP`` (SPY, QQQ,
  IWB, IWM, DIA) -- tickers with real ``EODPrice`` history in this DB via
  the ``polygon_eod`` connector. ``benchmark_type="INDEX"``, ``ticker`` set,
  ``constituents`` left null (the index isn't reconstructed from parts --
  its proxy ETF price series stands in for it).
* User-created custom benchmarks/indices (``CustomIndexBuilder.tsx``),
  ``benchmark_type="CUSTOM"``, ``ticker`` null, ``constituents`` a JSONB
  list of ``{"ticker": ..., "weight": ...}`` pairs.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Benchmark(TimestampMixin, Base):
    """A benchmark: a standard index (ETF-proxy tracked) or a user-created
    custom weighted index.
    """

    __tablename__ = "benchmarks"

    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Short, URL/slug-safe identifier, e.g. "SP500" or a slugified custom name.
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    # Underlying tradeable proxy ticker for standard indices (e.g. "SPY").
    # Null for custom benchmarks, whose performance is derived from
    # `constituents` instead.
    ticker: Mapped[str | None] = mapped_column(String(20))
    benchmark_type: Mapped[str] = mapped_column(String(20), nullable=False, default="INDEX")
    # Anonymous/system benchmarks (standard indices) have no owner. Custom
    # benchmarks are attributed to the creating user when auth is present
    # (REQUIRE_AUTH is False by default in this app -- see src/config.py --
    # so this is commonly null even for custom rows today).
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    # [{"ticker": "AAPL", "weight": 0.25}, ...] for user-built custom
    # indices. Null for standard indices (tracked via `ticker` instead).
    constituents: Mapped[list | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("benchmark_type IN ('INDEX', 'CUSTOM')", name="ck_benchmark_type"),
    )
