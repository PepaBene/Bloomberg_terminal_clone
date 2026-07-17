"""Standard benchmark index model (Pillar 2 Frontend Bugs 93-95).

``GET /v1/benchmarks`` and ``POST /v1/benchmarks`` were declared in
``frontend/src/api/endpoints.ts`` and consumed by ``CustomIndexBuilder.tsx``
/ the quant benchmark hooks, but had no backing model or router anywhere in
``src/`` -- a permanent 404, not a wiring bug.

This model tracks standard market indices only (S&P 500, NASDAQ 100,
Russell 1000/2000, Dow), via the same tradeable-ETF-proxy idea already used
by ``scripts/run_backtest_worker.py``'s ``_BENCHMARK_TICKER_MAP`` (SPY, QQQ,
IWB, IWM, DIA) -- tickers with real ``EODPrice`` history in this DB via the
``polygon_eod`` connector.

User-created custom benchmarks/indices were originally modeled as a second
row-type on this same table (``benchmark_type="CUSTOM"``, a JSONB
``constituents`` blob). That duplicated a pre-existing, more capable
``CustomIndex``/``IndexConstituent`` system (``src/models/custom_index.py``,
``src/engines/custom_index.py``) that already supports real weighting
methods, rebalancing, and persisted performance history -- but had zero
frontend consumers. ``src/api/routers/benchmarks.py`` now delegates all
custom-index creation/reads to that existing system instead, so this model
only ever represents ``INDEX``-type rows.
"""

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Benchmark(TimestampMixin, Base):
    """A standard market index, tracked via a tradeable ETF proxy ticker."""

    __tablename__ = "benchmarks"

    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Short, URL/slug-safe identifier, e.g. "SP500".
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    # Underlying tradeable proxy ticker (e.g. "SPY").
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
