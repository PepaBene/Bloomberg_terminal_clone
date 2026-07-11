"""Benchmarks API (Pillar 2 Frontend Bugs 93-95).

``GET /v1/benchmarks`` and ``POST /v1/benchmarks`` were declared in
``frontend/src/api/endpoints.ts`` and consumed by ``CustomIndexBuilder.tsx``
/ the quant benchmark hooks (``useBenchmarks`` etc., ``frontend/src/api/
hooks/useQuant.ts``), but had no backing model or router anywhere in
``src/`` -- a permanent 404, not a wiring bug.

Two kinds of benchmark are served:

* Standard indices (S&P 500, NASDAQ 100, Russell 1000, Russell 2000, Dow),
  tracked via the same tradeable-ETF-proxy idea already used by
  ``scripts/run_backtest_worker.py``'s ``_BENCHMARK_TICKER_MAP`` (SPY, QQQ,
  IWB, IWM, DIA) -- tickers with real ``EODPrice`` history in this DB via
  the ``polygon_eod`` connector. They're lazily seeded into the
  ``benchmarks`` table the first time anyone lists benchmarks.
* User-created custom benchmarks (``POST /v1/benchmarks``), persisted with
  a JSONB list of ``{"ticker": ..., "weight": ...}`` constituents.

Performance (``GET /{id}/returns``) is computed for real from ``EODPrice``
history through ``compute_performance_metrics`` -- the same function the
backtest worker uses -- for either a single proxy ticker (standard index)
or a real weight-averaged daily-return series built from constituent
prices (custom index). No fabricated numbers: if a ticker/constituent has
no EOD history in the requested range, the response says so explicitly
via ``unresolved_tickers`` or a 404, rather than inventing a number.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.backtester import compute_performance_metrics
from src.models.benchmark import Benchmark
from src.models.security import EODPrice, SecurityIdentifier

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])

# Standard indices, tracked via the same tradeable ETF proxy tickers as
# scripts/run_backtest_worker.py::_BENCHMARK_TICKER_MAP.
_STANDARD_INDICES: list[dict[str, str]] = [
    {"code": "SP500", "name": "S&P 500", "ticker": "SPY"},
    {"code": "NASDAQ100", "name": "NASDAQ 100", "ticker": "QQQ"},
    {"code": "RUSSELL1000", "name": "Russell 1000", "ticker": "IWB"},
    {"code": "RUSSELL2000", "name": "Russell 2000", "ticker": "IWM"},
    {"code": "DOW", "name": "Dow Jones Industrial Average", "ticker": "DIA"},
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BenchmarkConstituentIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    weight: float = Field(gt=0, le=1)


class CreateBenchmarkRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    constituents: list[BenchmarkConstituentIn] = Field(min_length=1)


class BenchmarkSummary(BaseModel):
    benchmark_id: uuid.UUID
    name: str
    code: str
    ticker: str | None = None
    benchmark_type: str
    constituent_count: int | None = None
    created_at: str | None = None


class BenchmarkDetail(BenchmarkSummary):
    constituents: list[dict] | None = None


class BenchmarkReturnsResponse(BaseModel):
    benchmark_id: uuid.UUID
    start_date: date
    end_date: date
    trading_days: int
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float | None = None
    max_drawdown: float
    monthly_returns: dict[str, float]
    unresolved_tickers: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify_code(name: str) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return code[:50] or "CUSTOM"


def _to_summary(row: Benchmark) -> BenchmarkSummary:
    return BenchmarkSummary(
        benchmark_id=row.benchmark_id,
        name=row.name,
        code=row.code,
        ticker=row.ticker,
        benchmark_type=row.benchmark_type,
        constituent_count=len(row.constituents) if row.constituents else None,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


def _to_detail(row: Benchmark) -> BenchmarkDetail:
    return BenchmarkDetail(**_to_summary(row).model_dump(), constituents=row.constituents)


async def _ensure_standard_indices_seeded(session: AsyncSession) -> None:
    existing_codes = set(
        (
            await session.execute(
                select(Benchmark.code).where(Benchmark.benchmark_type == "INDEX")
            )
        ).scalars().all()
    )
    missing = [idx for idx in _STANDARD_INDICES if idx["code"] not in existing_codes]
    if not missing:
        return
    for idx in missing:
        session.add(Benchmark(
            benchmark_id=uuid.uuid4(),
            name=idx["name"],
            code=idx["code"],
            ticker=idx["ticker"],
            benchmark_type="INDEX",
        ))
    await session.commit()


async def _security_id_for_ticker(session: AsyncSession, ticker: str) -> uuid.UUID | None:
    return (
        await session.execute(
            select(SecurityIdentifier.security_id).where(
                SecurityIdentifier.identifier_type == "TICKER",
                SecurityIdentifier.identifier_value == ticker.upper(),
            ).limit(1)
        )
    ).scalar_one_or_none()


async def _price_series_for_ticker(
    session: AsyncSession, ticker: str, start: date, end: date,
) -> dict[date, float] | None:
    """Real ``{price_date: close}`` series for ``ticker``, or None if unresolved."""
    sid = await _security_id_for_ticker(session, ticker)
    if sid is None:
        return None
    rows = (
        await session.execute(
            select(EODPrice.price_date, EODPrice.close_adjusted, EODPrice.close)
            .where(
                EODPrice.security_id == sid,
                EODPrice.price_date >= start,
                EODPrice.price_date <= end,
            )
            .order_by(EODPrice.price_date)
        )
    ).all()
    series: dict[date, float] = {}
    for d, close_adj, close in rows:
        px = float(close_adj) if close_adj is not None else (float(close) if close is not None else None)
        if px is not None and px > 0:
            series[d] = px
    return series or None


def _returns_from_series(dates: list[date], series: dict[date, float]) -> list[float]:
    returns = [0.0]
    prev = series.get(dates[0])
    for d in dates[1:]:
        px = series.get(d)
        if px is not None and prev is not None and prev > 0:
            returns.append((px - prev) / prev)
            prev = px
        else:
            returns.append(0.0)
            if px is not None:
                prev = px
    return returns


def _monthly_returns(dates: list[date], returns: list[float]) -> dict[str, float]:
    buckets: dict[str, float] = {}
    for d, r in zip(dates, returns):
        key = d.strftime("%Y-%m")
        buckets[key] = (1 + buckets[key]) * (1 + r) - 1 if key in buckets else r
    return {k: round(v, 6) for k, v in buckets.items()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BenchmarkSummary])
async def list_benchmarks(session: AsyncSession = Depends(get_session)):
    """List standard market indices plus any user-created custom benchmarks."""
    await _ensure_standard_indices_seeded(session)
    rows = (
        await session.execute(
            select(Benchmark).order_by(Benchmark.benchmark_type, Benchmark.name)
        )
    ).scalars().all()
    return [_to_summary(r) for r in rows]


@router.post("", response_model=BenchmarkDetail, status_code=201)
async def create_benchmark(
    body: CreateBenchmarkRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom weighted benchmark/index (``CustomIndexBuilder.tsx``)."""
    tickers = [c.ticker.upper() for c in body.constituents]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(status_code=422, detail="Duplicate tickers in constituents")

    total_weight = sum(c.weight for c in body.constituents)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=f"Constituent weights must sum to 1.0 (got {total_weight:.4f})",
        )

    code = _slugify_code(body.name)
    existing_codes = set((await session.execute(select(Benchmark.code))).scalars().all())
    if code in existing_codes:
        code = f"{code}_{uuid.uuid4().hex[:6]}"

    benchmark = Benchmark(
        benchmark_id=uuid.uuid4(),
        name=body.name,
        code=code,
        ticker=None,
        benchmark_type="CUSTOM",
        constituents=[{"ticker": t, "weight": c.weight} for t, c in zip(tickers, body.constituents)],
    )
    session.add(benchmark)
    await session.commit()
    await session.refresh(benchmark)
    return _to_detail(benchmark)


@router.get("/{benchmark_id}", response_model=BenchmarkDetail)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single benchmark's definition."""
    row = (
        await session.execute(select(Benchmark).where(Benchmark.benchmark_id == benchmark_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return _to_detail(row)


@router.get("/{benchmark_id}/returns", response_model=BenchmarkReturnsResponse)
async def get_benchmark_returns(
    benchmark_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start_date: date | None = Query(None, description="Defaults to 1 year before end_date"),
    end_date: date | None = Query(None, description="Defaults to today"),
):
    """Real performance for a benchmark, computed from EODPrice history.

    Standard indices use their proxy ETF's price series directly. Custom
    indices compute a weight-averaged daily-return series from constituent
    EOD prices (weights renormalized over whichever constituents actually
    have price history in range -- unresolved ones are reported, not
    silently dropped).
    """
    row = (
        await session.execute(select(Benchmark).where(Benchmark.benchmark_id == benchmark_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    end = end_date or date.today()
    start = start_date or (end - timedelta(days=365))
    if start >= end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")

    unresolved: list[str] = []
    daily_returns: list[float]
    dates: list[date]

    if row.benchmark_type == "INDEX" and row.ticker:
        series = await _price_series_for_ticker(session, row.ticker, start, end)
        if not series:
            raise HTTPException(
                status_code=404,
                detail=f"No EOD price history found for {row.ticker} in the requested range.",
            )
        dates = sorted(series)
        if len(dates) < 2:
            raise HTTPException(status_code=404, detail="Insufficient EOD price history in the requested range.")
        daily_returns = _returns_from_series(dates, series)
    else:
        constituents = row.constituents or []
        if not constituents:
            raise HTTPException(status_code=400, detail="Benchmark has no constituents to compute performance from")

        per_ticker: dict[str, tuple[dict[date, float], float]] = {}
        for c in constituents:
            s = await _price_series_for_ticker(session, c["ticker"], start, end)
            if s:
                per_ticker[c["ticker"]] = (s, float(c["weight"]))
            else:
                unresolved.append(c["ticker"])
        if not per_ticker:
            raise HTTPException(
                status_code=404,
                detail="No EOD price history found for any constituent ticker in the requested range.",
            )

        all_dates: set[date] = set()
        for s, _ in per_ticker.values():
            all_dates.update(s.keys())
        dates = sorted(d for d in all_dates if start <= d <= end)
        if len(dates) < 2:
            raise HTTPException(status_code=404, detail="Insufficient EOD price history in the requested range.")

        total_w = sum(w for _, w in per_ticker.values())
        daily_returns = [0.0]
        prev_prices = {t: s.get(dates[0]) for t, (s, _) in per_ticker.items()}
        for d in dates[1:]:
            day_return = 0.0
            for t, (s, w) in per_ticker.items():
                p0 = prev_prices.get(t)
                p1 = s.get(d)
                if p0 is not None and p1 is not None and p0 > 0:
                    day_return += (w / total_w) * (p1 / p0 - 1.0)
                if p1 is not None:
                    prev_prices[t] = p1
            daily_returns.append(day_return)

    perf = compute_performance_metrics(daily_returns)
    return BenchmarkReturnsResponse(
        benchmark_id=benchmark_id,
        start_date=dates[0],
        end_date=dates[-1],
        trading_days=len(dates),
        total_return=perf.total_return,
        annualized_return=perf.annualized_return,
        annualized_volatility=perf.annualized_volatility,
        sharpe_ratio=perf.sharpe_ratio,
        max_drawdown=perf.max_drawdown,
        monthly_returns=_monthly_returns(dates, daily_returns),
        unresolved_tickers=unresolved,
    )
