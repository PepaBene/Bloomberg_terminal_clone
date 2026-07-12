"""Benchmarks API (Pillar 2 Frontend Bugs 93-95).

``GET /v1/benchmarks`` and ``POST /v1/benchmarks`` were declared in
``frontend/src/api/endpoints.ts`` and consumed by ``CustomIndexBuilder.tsx``
/ the quant benchmark hooks (``useBenchmarks`` etc., ``frontend/src/api/
hooks/useQuant.ts``), but had no backing model or router anywhere in
``src/`` -- a permanent 404, not a wiring bug.

Two kinds of benchmark are served, from two different tables:

* Standard indices (S&P 500, NASDAQ 100, Russell 1000, Russell 2000, Dow),
  tracked via the same tradeable-ETF-proxy idea already used by
  ``scripts/run_backtest_worker.py``'s ``_BENCHMARK_TICKER_MAP`` (SPY, QQQ,
  IWB, IWM, DIA) -- tickers with real ``EODPrice`` history in this DB via
  the ``polygon_eod`` connector. Backed by the ``Benchmark`` model,
  lazily seeded into the ``benchmarks`` table the first time anyone lists
  benchmarks.
* User-created custom benchmarks (``POST /v1/benchmarks``). These are
  backed by the pre-existing ``CustomIndex``/``IndexConstituent`` system
  (``src/models/custom_index.py``, ``src/engines/custom_index.py``,
  originally built for -- and still separately exposed at --
  ``src/api/routers/custom_index.py``'s ``/analytics/indices`` endpoints)
  instead of a second, weaker parallel model. That system already has real
  weighting-method support, rebalancing fields, and a persisted performance
  engine; an earlier pass at this feature duplicated a much simpler
  JSONB-blob version of the same concept on the ``Benchmark`` table before
  this consolidation, discovered to have zero frontend consumers of its
  own. This router is now just a second, unified-shape API surface over
  ``CustomIndex`` for the ``/v1/benchmarks`` contract the frontend already
  expects -- it does not duplicate storage or computation.

Performance (``GET /{id}/returns``) is computed for real from ``EODPrice``
history through ``compute_performance_metrics`` -- the same function the
backtest worker uses -- for either a single proxy ticker (standard index)
or a real weight-averaged daily-return series built from constituent
prices (custom index, via its real ``IndexConstituent`` weights). No
fabricated numbers: if a ticker/constituent has no EOD history in the
requested range, the response says so explicitly via
``unresolved_tickers`` or a 404, rather than inventing a number.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.backtester import compute_performance_metrics
from src.models.benchmark import Benchmark
from src.models.custom_index import CustomIndex, IndexConstituent
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


def _index_to_summary(row: CustomIndex, constituent_count: int) -> BenchmarkSummary:
    """Map a CustomIndex row onto the shared BenchmarkSummary shape."""
    return BenchmarkSummary(
        benchmark_id=row.index_id,
        name=row.name,
        code=_slugify_code(row.name),
        ticker=None,
        benchmark_type="CUSTOM",
        constituent_count=constituent_count or None,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


def _benchmark_to_summary(row: Benchmark) -> BenchmarkSummary:
    return BenchmarkSummary(
        benchmark_id=row.benchmark_id,
        name=row.name,
        code=row.code,
        ticker=row.ticker,
        benchmark_type="INDEX",
        constituent_count=None,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


async def _ensure_standard_indices_seeded(session: AsyncSession) -> None:
    existing_codes = set(
        (await session.execute(select(Benchmark.code))).scalars().all()
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


async def _tickers_for_security_ids(
    session: AsyncSession, security_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not security_ids:
        return {}
    rows = (
        await session.execute(
            select(SecurityIdentifier.security_id, SecurityIdentifier.identifier_value).where(
                SecurityIdentifier.security_id.in_(security_ids),
                SecurityIdentifier.identifier_type == "TICKER",
            )
        )
    ).all()
    return {sid: ticker for sid, ticker in rows}


async def _price_series_for_security(
    session: AsyncSession, security_id: uuid.UUID, start: date, end: date,
) -> dict[date, float] | None:
    """Real ``{price_date: close}`` series for ``security_id``, or None if empty."""
    rows = (
        await session.execute(
            select(EODPrice.price_date, EODPrice.close_adjusted, EODPrice.close)
            .where(
                EODPrice.security_id == security_id,
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


async def _price_series_for_ticker(
    session: AsyncSession, ticker: str, start: date, end: date,
) -> dict[date, float] | None:
    sid = await _security_id_for_ticker(session, ticker)
    if sid is None:
        return None
    return await _price_series_for_security(session, sid, start, end)


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
    """List standard market indices plus any user-created custom indices."""
    await _ensure_standard_indices_seeded(session)
    index_rows = (
        await session.execute(
            select(Benchmark).order_by(Benchmark.name)
        )
    ).scalars().all()

    custom_rows = (
        await session.execute(
            select(CustomIndex)
            .where(CustomIndex.status == "ACTIVE")
            .order_by(CustomIndex.name)
        )
    ).scalars().all()
    counts: dict[uuid.UUID, int] = {}
    if custom_rows:
        count_rows = (
            await session.execute(
                select(IndexConstituent.index_id, func.count())
                .where(
                    IndexConstituent.index_id.in_([r.index_id for r in custom_rows]),
                    IndexConstituent.is_active == True,  # noqa: E712
                )
                .group_by(IndexConstituent.index_id)
            )
        ).all()
        counts = dict(count_rows)

    return [_benchmark_to_summary(r) for r in index_rows] + [
        _index_to_summary(r, counts.get(r.index_id, 0)) for r in custom_rows
    ]


@router.post("", response_model=BenchmarkDetail, status_code=201)
async def create_benchmark(
    body: CreateBenchmarkRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom weighted benchmark/index (``CustomIndexBuilder.tsx``).

    Persisted via the existing ``CustomIndex``/``IndexConstituent`` system
    (real weighting-method/rebalance fields, a real performance engine)
    rather than a bespoke JSONB blob -- see module docstring.
    """
    tickers = [c.ticker.upper() for c in body.constituents]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(status_code=422, detail="Duplicate tickers in constituents")

    total_weight = sum(c.weight for c in body.constituents)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=f"Constituent weights must sum to 1.0 (got {total_weight:.4f})",
        )

    resolved: dict[str, uuid.UUID] = {}
    unresolved: list[str] = []
    for ticker in tickers:
        sid = await _security_id_for_ticker(session, ticker)
        if sid is None:
            unresolved.append(ticker)
        else:
            resolved[ticker] = sid
    if unresolved:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown ticker(s), no matching security: {', '.join(unresolved)}",
        )

    today = date.today()
    index = CustomIndex(
        index_id=uuid.uuid4(),
        name=body.name,
        status="ACTIVE",
        weighting_method="EQUAL" if len({c.weight for c in body.constituents}) == 1 else "CUSTOM",
        inception_date=today,
    )
    session.add(index)
    await session.flush()

    for c in body.constituents:
        session.add(IndexConstituent(
            constituent_id=uuid.uuid4(),
            index_id=index.index_id,
            security_id=resolved[c.ticker.upper()],
            weight=c.weight,
            added_date=today,
            is_active=True,
        ))
    await session.commit()

    return BenchmarkDetail(
        **_index_to_summary(index, len(body.constituents)).model_dump(),
        constituents=[
            {"ticker": c.ticker.upper(), "weight": c.weight} for c in body.constituents
        ],
    )


@router.get("/{benchmark_id}", response_model=BenchmarkDetail)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single benchmark's definition (standard index or custom index)."""
    index_row = (
        await session.execute(select(Benchmark).where(Benchmark.benchmark_id == benchmark_id))
    ).scalar_one_or_none()
    if index_row is not None:
        return BenchmarkDetail(**_benchmark_to_summary(index_row).model_dump(), constituents=None)

    custom_row = (
        await session.execute(select(CustomIndex).where(CustomIndex.index_id == benchmark_id))
    ).scalar_one_or_none()
    if custom_row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    constituent_rows = (
        await session.execute(
            select(IndexConstituent).where(
                IndexConstituent.index_id == benchmark_id,
                IndexConstituent.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    ticker_map = await _tickers_for_security_ids(
        session, [c.security_id for c in constituent_rows]
    )
    return BenchmarkDetail(
        **_index_to_summary(custom_row, len(constituent_rows)).model_dump(),
        constituents=[
            {
                "ticker": ticker_map.get(c.security_id),
                "security_id": str(c.security_id),
                "weight": float(c.weight) if c.weight is not None else None,
            }
            for c in constituent_rows
        ],
    )


@router.get("/{benchmark_id}/returns", response_model=BenchmarkReturnsResponse)
async def get_benchmark_returns(
    benchmark_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start_date: date | None = Query(None, description="Defaults to 1 year before end_date"),
    end_date: date | None = Query(None, description="Defaults to today"),
):
    """Real performance for a benchmark, computed from EODPrice history.

    Standard indices use their proxy ETF's price series directly. Custom
    indices compute a weight-averaged daily-return series from their real
    ``IndexConstituent`` weights and EOD prices (weights renormalized over
    whichever constituents actually have price history in range --
    unresolved ones are reported, not silently dropped).
    """
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=365))
    if start >= end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")

    index_row = (
        await session.execute(select(Benchmark).where(Benchmark.benchmark_id == benchmark_id))
    ).scalar_one_or_none()

    unresolved: list[str] = []
    daily_returns: list[float]
    dates: list[date]

    if index_row is not None:
        series = await _price_series_for_ticker(session, index_row.ticker, start, end)
        if not series:
            raise HTTPException(
                status_code=404,
                detail=f"No EOD price history found for {index_row.ticker} in the requested range.",
            )
        dates = sorted(series)
        if len(dates) < 2:
            raise HTTPException(status_code=404, detail="Insufficient EOD price history in the requested range.")
        daily_returns = _returns_from_series(dates, series)
    else:
        custom_row = (
            await session.execute(select(CustomIndex).where(CustomIndex.index_id == benchmark_id))
        ).scalar_one_or_none()
        if custom_row is None:
            raise HTTPException(status_code=404, detail="Benchmark not found")

        constituents = (
            await session.execute(
                select(IndexConstituent).where(
                    IndexConstituent.index_id == benchmark_id,
                    IndexConstituent.is_active == True,  # noqa: E712
                    IndexConstituent.weight.isnot(None),
                )
            )
        ).scalars().all()
        if not constituents:
            raise HTTPException(status_code=400, detail="Benchmark has no active weighted constituents")

        ticker_map = await _tickers_for_security_ids(session, [c.security_id for c in constituents])
        per_security: dict[uuid.UUID, tuple[dict[date, float], float]] = {}
        for c in constituents:
            s = await _price_series_for_security(session, c.security_id, start, end)
            if s:
                per_security[c.security_id] = (s, float(c.weight))
            else:
                unresolved.append(ticker_map.get(c.security_id, str(c.security_id)))
        if not per_security:
            raise HTTPException(
                status_code=404,
                detail="No EOD price history found for any constituent in the requested range.",
            )

        all_dates: set[date] = set()
        for s, _ in per_security.values():
            all_dates.update(s.keys())
        dates = sorted(d for d in all_dates if start <= d <= end)
        if len(dates) < 2:
            raise HTTPException(status_code=404, detail="Insufficient EOD price history in the requested range.")

        total_w = sum(w for _, w in per_security.values())
        daily_returns = [0.0]
        prev_prices = {sid: s.get(dates[0]) for sid, (s, _) in per_security.items()}
        for d in dates[1:]:
            day_return = 0.0
            for sid, (s, w) in per_security.items():
                p0 = prev_prices.get(sid)
                p1 = s.get(d)
                if p0 is not None and p1 is not None and p0 > 0:
                    day_return += (w / total_w) * (p1 / p0 - 1.0)
                if p1 is not None:
                    prev_prices[sid] = p1
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
