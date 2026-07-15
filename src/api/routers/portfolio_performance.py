"""Portfolio Performance & Attribution API endpoints (Pillar 4 Phase 2)."""

import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.engines import performance_engine
from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.security import EODPrice, SecurityIdentifier
from src.models.transaction import Transaction
from src.models.nav_snapshot import NAVSnapshot
from src.models.performance import PerformanceSnapshot
from src.models.attribution import AttributionResult, ReportRequest
from src.schemas.performance import (
    BenchmarkComparisonResponse,
    CalendarReturnEntry,
    CalendarReturnResponse,
    DrawdownResponse,
    PerformanceCompareEntry,
    PerformanceCompareResponse,
    PerformanceResponse,
    ReturnSeriesEntry,
    ReturnSeriesResponse,
    RiskMetricsResponse,
    RollingReturnEntry,
    RollingReturnResponse,
)
from src.schemas.attribution import (
    AttributionResponse,
    BrinsonResponse,
    FactorAttributionEntry,
    SectorAttributionEntry,
    SecurityContributionEntry,
)
from src.schemas.reporting import (
    ExportResponse,
    ReportGenerateRequest,
    ReportResponse,
)

router = APIRouter(tags=["Portfolio Performance"])


def _rows_to_csv(header: list[str], rows: list[list]) -> str:
    """Render a header + rows into a properly escaped/quoted CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_portfolio(session: AsyncSession, portfolio_id: uuid.UUID) -> Portfolio:
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


def _opt_float(val) -> float | None:
    if val is None:
        return None
    return float(val)


def _perf_to_response(snap: PerformanceSnapshot) -> PerformanceResponse:
    return PerformanceResponse(
        id=snap.id,
        portfolio_id=snap.portfolio_id,
        period_type=snap.period_type,
        period_start=snap.period_start,
        period_end=snap.period_end,
        twr_return=_opt_float(snap.twr_return),
        mwr_return=_opt_float(snap.mwr_return),
        benchmark_return=_opt_float(snap.benchmark_return),
        active_return=_opt_float(snap.active_return),
        sharpe_ratio=_opt_float(snap.sharpe_ratio),
        sortino_ratio=_opt_float(snap.sortino_ratio),
        information_ratio=_opt_float(snap.information_ratio),
        tracking_error=_opt_float(snap.tracking_error),
        max_drawdown=_opt_float(snap.max_drawdown),
        calmar_ratio=_opt_float(snap.calmar_ratio),
        beta=_opt_float(snap.beta),
        alpha=_opt_float(snap.alpha),
        volatility=_opt_float(snap.volatility),
        up_capture=_opt_float(snap.up_capture),
        down_capture=_opt_float(snap.down_capture),
        batting_average=_opt_float(snap.batting_average),
        best_day=_opt_float(snap.best_day),
        worst_day=_opt_float(snap.worst_day),
        positive_days=snap.positive_days,
        negative_days=snap.negative_days,
    )


# ── NAV / performance computation ────────────────────────────────────
#
# Nothing in the codebase ever wrote a NAVSnapshot or PerformanceSnapshot
# row in production — every read endpoint below queried tables that stayed
# permanently empty. These helpers wire up nav_engine and the previously
# orphaned performance_engine (TWR/MWR/Sharpe/Sortino/drawdown/etc, all
# real, unit-tested pure computation) against real position/price data.


async def _ensure_nav_snapshot_today(session: AsyncSession, portfolio_id: uuid.UUID) -> NAVSnapshot:
    """Idempotently record today's NAV snapshot from real position data."""
    # Local import: avoids a circular import (portfolios.py doesn't import
    # this module) while reusing the real market-value refresh logic.
    from src.api.routers.portfolios import _refresh_portfolio_positions
    from src.engines import nav_engine

    today = date.today()
    existing_today = (
        await session.execute(
            select(NAVSnapshot).where(
                NAVSnapshot.portfolio_id == portfolio_id,
                NAVSnapshot.snapshot_date == today,
            )
        )
    ).scalar_one_or_none()
    if existing_today:
        return existing_today

    portfolio = await _get_portfolio(session, portfolio_id)
    await _refresh_portfolio_positions(session, portfolio_id)

    pos_rows = (
        await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.status == "OPEN",
            )
        )
    ).scalars().all()
    market_value = sum(float(p.market_value) for p in pos_rows if p.market_value is not None)
    unrealized_pnl = sum(float(p.unrealized_pnl) for p in pos_rows if p.unrealized_pnl is not None)
    cash = float(portfolio.current_cash or 0)
    nav = market_value + cash

    prior = (
        await session.execute(
            select(NAVSnapshot)
            .where(NAVSnapshot.portfolio_id == portfolio_id, NAVSnapshot.snapshot_date < today)
            .order_by(NAVSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    daily_return = 0.0
    cumulative_return = 0.0
    if prior is not None and float(prior.nav) > 0:
        daily_return = nav_engine.compute_daily_return(nav, float(prior.nav))
        cumulative_return = (1.0 + float(prior.cumulative_return or 0.0)) * (1.0 + daily_return) - 1.0

    snap = NAVSnapshot(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        snapshot_date=today,
        nav=Decimal(str(round(nav, 2))),
        market_value=Decimal(str(round(market_value, 2))),
        cash_balance=Decimal(str(round(cash, 2))),
        unrealized_pnl=Decimal(str(round(unrealized_pnl, 2))),
        daily_return=Decimal(str(round(daily_return, 6))),
        cumulative_return=Decimal(str(round(cumulative_return, 6))),
    )
    session.add(snap)
    await session.commit()
    await session.refresh(snap)
    return snap


def _dec_or_none(val: float | None, places: int = 6) -> Decimal | None:
    return Decimal(str(round(val, places))) if val is not None else None


async def _resolve_benchmark_security_id(
    session: AsyncSession, ticker: str
) -> uuid.UUID | None:
    """Resolve a free-text benchmark ticker (Portfolio.benchmark_id, e.g.
    "SPY"/"^GSPC") to a real Security via its TICKER identifier.

    Reuses the exact same TICKER-identifier lookup already established for
    position tickers (src.api.routers.portfolios._resolve_security_id) and
    for benchmark tickers elsewhere (src.api.routers.risk
    ._resolve_benchmark_security_id) rather than inventing a new pattern.
    Returns None (rather than raising) when the ticker isn't registered as a
    SecurityIdentifier — an unresolvable benchmark is an honest gap, not an
    error that should break the rest of performance computation.
    """
    result = await session.execute(
        select(SecurityIdentifier.security_id).where(
            SecurityIdentifier.identifier_type == "TICKER",
            SecurityIdentifier.identifier_value == ticker.upper(),
        )
    )
    return result.scalar_one_or_none()


async def _build_benchmark_history(
    session: AsyncSession, security_id: uuid.UUID, nav_dates: list[date]
) -> list[dict] | None:
    """Build a benchmark price series aligned 1:1 to ``nav_dates``.

    performance_engine.build_performance_summary() only computes
    benchmark-relative metrics when ``len(benchmark_history) ==
    len(nav_history)`` and zips the two lists index-by-index — so this only
    returns a series when *every* NAV date has a matching EODPrice row for
    the resolved benchmark security. A partial/gappy match would silently
    misalign dates to the wrong daily return, which is worse than no
    benchmark data at all. When coverage is incomplete, returns None so the
    caller leaves benchmark-relative fields null (an honest gap) instead of
    fabricating a misaligned comparison.
    """
    if not nav_dates:
        return None
    rows = (
        await session.execute(
            select(EODPrice.price_date, EODPrice.close).where(
                EODPrice.security_id == security_id,
                EODPrice.price_date >= nav_dates[0],
                EODPrice.price_date <= nav_dates[-1],
                EODPrice.close.isnot(None),
            )
        )
    ).all()
    price_by_date = {r.price_date: float(r.close) for r in rows}
    if not all(d in price_by_date for d in nav_dates):
        return None
    return [{"date": d.isoformat(), "nav": price_by_date[d]} for d in nav_dates]


async def _resolve_benchmark_history(
    session: AsyncSession, portfolio: Portfolio, nav_dates: list[date]
) -> list[dict] | None:
    """End-to-end: Portfolio.benchmark_id ticker -> Security -> EODPrice
    series aligned to ``nav_dates``, or None when unresolvable/incomplete.
    """
    if not portfolio.benchmark_id:
        return None
    security_id = await _resolve_benchmark_security_id(session, portfolio.benchmark_id)
    if security_id is None:
        return None
    return await _build_benchmark_history(session, security_id, nav_dates)


def _summary_to_fields(summary: performance_engine.PerformanceSummary) -> dict:
    """Map a PerformanceSummary onto PerformanceSnapshot column values.

    Shared by the live per-request computation below and the historical
    backfill script (scripts/backfill_performance_snapshots.py) so both
    write identical column semantics from the same engine output.
    """
    return dict(
        twr_return=_dec_or_none(summary.twr_return, 8),
        mwr_return=_dec_or_none(summary.mwr_return, 8),
        benchmark_return=_dec_or_none(summary.benchmark_return, 8),
        active_return=_dec_or_none(summary.active_return, 8),
        max_drawdown=_dec_or_none(summary.drawdown.max_drawdown),
        sharpe_ratio=_dec_or_none(summary.risk_metrics.sharpe_ratio),
        sortino_ratio=_dec_or_none(summary.risk_metrics.sortino_ratio),
        information_ratio=_dec_or_none(summary.risk_metrics.information_ratio),
        tracking_error=_dec_or_none(summary.risk_metrics.tracking_error),
        calmar_ratio=_dec_or_none(summary.risk_metrics.calmar_ratio),
        beta=_dec_or_none(summary.risk_metrics.beta),
        alpha=_dec_or_none(summary.risk_metrics.alpha),
        volatility=_dec_or_none(summary.risk_metrics.volatility),
        up_capture=_dec_or_none(summary.risk_metrics.up_capture),
        down_capture=_dec_or_none(summary.risk_metrics.down_capture),
        batting_average=_dec_or_none(summary.risk_metrics.batting_average),
        best_day=_dec_or_none(summary.best_day, 8),
        worst_day=_dec_or_none(summary.worst_day, 8),
        positive_days=summary.positive_days,
        negative_days=summary.negative_days,
    )


async def _upsert_performance_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    period_type: str,
    period_start: date,
    period_end: date,
    fields: dict,
) -> PerformanceSnapshot:
    """Idempotent upsert keyed on (portfolio_id, period_type, period_end) —
    matches the model's own uq_perf_portfolio_type_end constraint, so this
    is safe to call repeatedly for the same day (or the same historical day
    during a backfill re-run) without creating duplicate rows.

    Does not commit — callers control transaction boundaries (a single
    request vs. a multi-portfolio/multi-day backfill batch).
    """
    existing = (
        await session.execute(
            select(PerformanceSnapshot).where(
                PerformanceSnapshot.portfolio_id == portfolio_id,
                PerformanceSnapshot.period_type == period_type,
                PerformanceSnapshot.period_end == period_end,
            )
        )
    ).scalar_one_or_none()

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        existing.period_start = period_start
        snap = existing
    else:
        snap = PerformanceSnapshot(
            id=uuid.uuid4(),
            portfolio_id=portfolio_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            **fields,
        )
        session.add(snap)
    return snap


async def _compute_and_persist_performance(
    session: AsyncSession, portfolio_id: uuid.UUID
) -> PerformanceSnapshot | None:
    """Build and persist a real "since-inception-to-date" DAILY performance
    snapshot from NAV history via performance_engine.build_performance_summary().

    Returns None when there's fewer than two NAV snapshots (not enough
    history yet to derive a return series) rather than fabricating one.

    Because this runs once per calendar day (period_end tracks "today",
    which advances with each new NAVSnapshot), repeated calls upsert the
    *same* row for a given day but a *new* row each subsequent day — so
    DAILY history genuinely accumulates one row per day over time. Prior
    days are backfilled in bulk by scripts/backfill_performance_snapshots.py
    (see src/scheduler/batch_config.py's performance_snapshot_backfill job)
    rather than here, since re-deriving the whole history on every request
    would be wasteful.

    Benchmark-relative metrics (benchmark_return, beta, alpha, tracking
    error, information ratio, up/down capture, batting average) are
    computed for real when Portfolio.benchmark_id resolves to a Security
    with full EODPrice coverage over the NAV date range (see
    _resolve_benchmark_history). When it doesn't resolve, or coverage is
    incomplete, those fields are left null — an honest gap rather than a
    guess.

    The sole external cash flow modeled is the portfolio's initial_cash at
    inception — this portfolio model has no deposit/withdrawal transaction
    type distinct from BUY/SELL (which are internal, NAV-neutral), so MWR
    computed this way is exact for the "no subsequent external flows" case
    and reduces to (very close to) TWR otherwise.
    """
    await _ensure_nav_snapshot_today(session, portfolio_id)
    portfolio = await _get_portfolio(session, portfolio_id)

    nav_rows = (
        await session.execute(
            select(NAVSnapshot)
            .where(NAVSnapshot.portfolio_id == portfolio_id)
            .order_by(NAVSnapshot.snapshot_date.asc())
        )
    ).scalars().all()
    if len(nav_rows) < 2:
        return None

    nav_history = [{"date": r.snapshot_date.isoformat(), "nav": float(r.nav)} for r in nav_rows]
    nav_dates = [r.snapshot_date for r in nav_rows]

    cash_flows = None
    if portfolio.initial_cash is not None and float(portfolio.initial_cash) > 0:
        cash_flows = [{"date_offset": 0, "amount": -float(portfolio.initial_cash)}]

    benchmark_history = await _resolve_benchmark_history(session, portfolio, nav_dates)

    summary = performance_engine.build_performance_summary(
        nav_history, benchmark_history=benchmark_history, cash_flows=cash_flows
    )

    period_start = nav_rows[0].snapshot_date
    period_end = nav_rows[-1].snapshot_date

    fields = _summary_to_fields(summary)
    snap = await _upsert_performance_snapshot(
        session, portfolio_id, "DAILY", period_start, period_end, fields
    )

    await session.commit()
    await session.refresh(snap)
    return snap


# ══════════════════════════════════════════════════════════════════════
# Static route — MUST be before /{portfolio_id} routes
# ══════════════════════════════════════════════════════════════════════


@router.get("/portfolios/performance/compare", response_model=PerformanceCompareResponse)
async def compare_portfolios(
    ids: str = Query(..., description="Comma-separated portfolio UUIDs"),
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """Compare performance across multiple portfolios.

    Restricted to portfolios owned by the caller (or the anonymous fallback
    user when REQUIRE_AUTH is off). Portfolios belonging to other users are
    silently dropped from the result.
    """
    # Match the same fallback identity as portfolios.py (``default_user``)
    # so unauthenticated callers can still compare their own portfolios.
    requester = user or "default_user"
    id_list = [uuid.UUID(x.strip()) for x in ids.split(",") if x.strip()]
    entries: list[PerformanceCompareEntry] = []

    for pid in id_list:
        # Get portfolio name
        p_result = await session.execute(
            select(Portfolio).where(Portfolio.id == pid)
        )
        portfolio = p_result.scalar_one_or_none()
        if not portfolio or portfolio.user_id != requester:
            continue

        snap = await _compute_and_persist_performance(session, pid)
        if not snap:
            snap_result = await session.execute(
                select(PerformanceSnapshot)
                .where(PerformanceSnapshot.portfolio_id == pid)
                .order_by(PerformanceSnapshot.period_end.desc())
                .limit(1)
            )
            snap = snap_result.scalar_one_or_none()

        entries.append(PerformanceCompareEntry(
            portfolio_id=pid,
            portfolio_name=portfolio.portfolio_name,
            twr_return=_opt_float(snap.twr_return) if snap else None,
            sharpe_ratio=_opt_float(snap.sharpe_ratio) if snap else None,
            max_drawdown=_opt_float(snap.max_drawdown) if snap else None,
            volatility=_opt_float(snap.volatility) if snap else None,
        ))

    return PerformanceCompareResponse(period=period, portfolios=entries)


# ══════════════════════════════════════════════════════════════════════
# Performance endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/performance",
    response_model=PerformanceResponse | None,
)
async def get_performance(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get latest performance snapshot for a portfolio."""
    await _get_portfolio(session, portfolio_id)
    snap = await _compute_and_persist_performance(session, portfolio_id)
    if not snap:
        # Not enough NAV history to compute fresh (e.g. a brand-new
        # portfolio) — fall back to whatever's already on record (a prior
        # batch-computed snapshot) instead of clobbering it with null.
        result = await session.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.portfolio_id == portfolio_id)
            .order_by(PerformanceSnapshot.period_end.desc())
            .limit(1)
        )
        snap = result.scalar_one_or_none()
    if not snap:
        return None
    return _perf_to_response(snap)


@router.get(
    "/portfolios/{portfolio_id}/performance/returns",
    response_model=ReturnSeriesResponse,
)
async def get_returns(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get return time series for a portfolio."""
    await _get_portfolio(session, portfolio_id)
    await _ensure_nav_snapshot_today(session, portfolio_id)

    result = await session.execute(
        select(NAVSnapshot)
        .where(NAVSnapshot.portfolio_id == portfolio_id)
        .order_by(NAVSnapshot.snapshot_date.asc())
    )
    rows = result.scalars().all()
    entries = [
        ReturnSeriesEntry(
            date=snap.snapshot_date,
            return_value=float(snap.daily_return) if snap.daily_return is not None else 0.0,
            cumulative_return=float(snap.cumulative_return) if snap.cumulative_return is not None else 0.0,
        )
        for snap in rows
    ]
    return ReturnSeriesResponse(
        portfolio_id=portfolio_id,
        period=period,
        entries=entries,
    )


@router.get(
    "/portfolios/{portfolio_id}/performance/returns/calendar",
    response_model=CalendarReturnResponse,
)
async def get_calendar_returns(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get calendar-year returns grid."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(
            PerformanceSnapshot.portfolio_id == portfolio_id,
            PerformanceSnapshot.period_type == "MONTHLY",
        )
        .order_by(PerformanceSnapshot.period_end.asc())
    )
    rows = result.scalars().all()

    # Group by year
    years_map: dict[int, CalendarReturnEntry] = {}
    month_attrs = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    for snap in rows:
        year = snap.period_end.year
        if year not in years_map:
            years_map[year] = CalendarReturnEntry(year=year)
        month_idx = snap.period_end.month - 1
        if 0 <= month_idx < 12:
            setattr(years_map[year], month_attrs[month_idx], _opt_float(snap.twr_return))

    return CalendarReturnResponse(
        portfolio_id=portfolio_id,
        years=list(years_map.values()),
    )


@router.get(
    "/portfolios/{portfolio_id}/performance/returns/rolling",
    response_model=RollingReturnResponse,
)
async def get_rolling_returns(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get rolling return series."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(
            PerformanceSnapshot.portfolio_id == portfolio_id,
            PerformanceSnapshot.period_type == "DAILY",
        )
        .order_by(PerformanceSnapshot.period_end.asc())
    )
    rows = result.scalars().all()
    entries = [
        RollingReturnEntry(
            date=snap.period_end,
            rolling_1m=_opt_float(snap.twr_return),
        )
        for snap in rows
    ]
    return RollingReturnResponse(portfolio_id=portfolio_id, entries=entries)


@router.get(
    "/portfolios/{portfolio_id}/performance/benchmark",
    response_model=BenchmarkComparisonResponse,
)
async def get_benchmark_comparison(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Compare portfolio to benchmark."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.portfolio_id == portfolio_id)
        .order_by(PerformanceSnapshot.period_end.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()

    return BenchmarkComparisonResponse(
        portfolio_id=portfolio_id,
        period=period,
        portfolio_return=_opt_float(snap.twr_return) if snap else 0.0,
        benchmark_return=_opt_float(snap.benchmark_return) if snap else 0.0,
        active_return=_opt_float(snap.active_return) if snap else 0.0,
        tracking_error=_opt_float(snap.tracking_error) if snap else None,
        information_ratio=_opt_float(snap.information_ratio) if snap else None,
    )


@router.get(
    "/portfolios/{portfolio_id}/performance/risk-metrics",
    response_model=RiskMetricsResponse,
)
async def get_risk_metrics(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get comprehensive risk metrics."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.portfolio_id == portfolio_id)
        .order_by(PerformanceSnapshot.period_end.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()

    return RiskMetricsResponse(
        portfolio_id=portfolio_id,
        period=period,
        sharpe_ratio=_opt_float(snap.sharpe_ratio) if snap else None,
        sortino_ratio=_opt_float(snap.sortino_ratio) if snap else None,
        information_ratio=_opt_float(snap.information_ratio) if snap else None,
        tracking_error=_opt_float(snap.tracking_error) if snap else None,
        beta=_opt_float(snap.beta) if snap else None,
        alpha=_opt_float(snap.alpha) if snap else None,
        volatility=_opt_float(snap.volatility) if snap else None,
        max_drawdown=_opt_float(snap.max_drawdown) if snap else None,
        calmar_ratio=_opt_float(snap.calmar_ratio) if snap else None,
        up_capture=_opt_float(snap.up_capture) if snap else None,
        down_capture=_opt_float(snap.down_capture) if snap else None,
    )


@router.get(
    "/portfolios/{portfolio_id}/performance/drawdown",
    response_model=DrawdownResponse,
)
async def get_drawdown(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get drawdown analysis."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.portfolio_id == portfolio_id)
        .order_by(PerformanceSnapshot.period_end.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()

    return DrawdownResponse(
        portfolio_id=portfolio_id,
        max_drawdown=_opt_float(snap.max_drawdown) if snap else None,
        peak_date=snap.period_start if snap else None,
        trough_date=snap.period_end if snap else None,
        recovery_date=None,
        duration_days=None,
    )


# ══════════════════════════════════════════════════════════════════════
# Attribution endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/attribution",
    response_model=AttributionResponse,
)
async def get_attribution(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get latest attribution result."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()

    if not attr:
        return AttributionResponse(
            portfolio_id=portfolio_id,
            period_start=date.today(),
            period_end=date.today(),
            brinson=None,
            factor_detail=[],
            top_contributors=[],
            bottom_contributors=[],
        )

    sector_entries = _parse_sector_detail(attr.sector_detail)
    factor_entries = _parse_factor_detail(attr.factor_detail)
    sec_entries = _parse_security_detail(attr.security_detail)
    sorted_sec = sorted(sec_entries, key=lambda x: x.contribution, reverse=True)

    brinson = BrinsonResponse(
        portfolio_id=portfolio_id,
        period_start=attr.period_start,
        period_end=attr.period_end,
        total_portfolio_return=_opt_float(attr.total_portfolio_return),
        total_benchmark_return=_opt_float(attr.total_benchmark_return),
        total_active_return=_opt_float(attr.total_active_return),
        total_allocation=_opt_float(attr.total_allocation),
        total_selection=_opt_float(attr.total_selection),
        total_interaction=_opt_float(attr.total_interaction),
        residual=_opt_float(attr.residual),
        sector_detail=sector_entries,
    )

    return AttributionResponse(
        portfolio_id=portfolio_id,
        period_start=attr.period_start,
        period_end=attr.period_end,
        brinson=brinson,
        factor_detail=factor_entries,
        top_contributors=sorted_sec[:5],
        bottom_contributors=sorted_sec[-5:] if len(sorted_sec) >= 5 else sorted_sec,
    )


@router.get(
    "/portfolios/{portfolio_id}/attribution/sectors",
    response_model=list[SectorAttributionEntry],
)
async def get_sector_attribution(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get sector-level Brinson attribution."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()
    if not attr:
        return []
    return _parse_sector_detail(attr.sector_detail)


@router.get(
    "/portfolios/{portfolio_id}/attribution/securities",
    response_model=list[SecurityContributionEntry],
)
async def get_security_attribution(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get security-level contribution analysis."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()
    if not attr:
        return []
    return _parse_security_detail(attr.security_detail)


@router.get(
    "/portfolios/{portfolio_id}/attribution/factors",
    response_model=list[FactorAttributionEntry],
)
async def get_factor_attribution(
    portfolio_id: uuid.UUID,
    period: str = Query(default="YTD"),
    session: AsyncSession = Depends(get_session),
):
    """Get factor attribution analysis."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()
    if not attr:
        return []
    return _parse_factor_detail(attr.factor_detail)


@router.get(
    "/portfolios/{portfolio_id}/contributors/best",
    response_model=list[SecurityContributionEntry],
)
async def get_best_contributors(
    portfolio_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Get best contributing securities."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()
    if not attr:
        return []
    sec = _parse_security_detail(attr.security_detail)
    return sorted(sec, key=lambda x: x.contribution, reverse=True)[:limit]


@router.get(
    "/portfolios/{portfolio_id}/contributors/worst",
    response_model=list[SecurityContributionEntry],
)
async def get_worst_contributors(
    portfolio_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Get worst contributing securities."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(AttributionResult)
        .where(AttributionResult.portfolio_id == portfolio_id)
        .order_by(AttributionResult.period_end.desc())
        .limit(1)
    )
    attr = result.scalar_one_or_none()
    if not attr:
        return []
    sec = _parse_security_detail(attr.security_detail)
    return sorted(sec, key=lambda x: x.contribution)[:limit]


# ══════════════════════════════════════════════════════════════════════
# Reports
# ══════════════════════════════════════════════════════════════════════


@router.post(
    "/portfolios/{portfolio_id}/reports/summary",
    response_model=ReportResponse,
    status_code=201,
)
async def generate_summary_report(
    portfolio_id: uuid.UUID,
    body: ReportGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate a portfolio summary report."""
    portfolio = await _get_portfolio(session, portfolio_id)
    return await _generate_report(session, portfolio, "SUMMARY", body)


@router.post(
    "/portfolios/{portfolio_id}/reports/performance",
    response_model=ReportResponse,
    status_code=201,
)
async def generate_performance_report(
    portfolio_id: uuid.UUID,
    body: ReportGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate a performance report."""
    portfolio = await _get_portfolio(session, portfolio_id)
    return await _generate_report(session, portfolio, "PERFORMANCE", body)


@router.post(
    "/portfolios/{portfolio_id}/reports/attribution",
    response_model=ReportResponse,
    status_code=201,
)
async def generate_attribution_report(
    portfolio_id: uuid.UUID,
    body: ReportGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate an attribution report."""
    portfolio = await _get_portfolio(session, portfolio_id)
    return await _generate_report(session, portfolio, "ATTRIBUTION", body)


@router.post(
    "/portfolios/{portfolio_id}/reports/holdings",
    response_model=ReportResponse,
    status_code=201,
)
async def generate_holdings_report(
    portfolio_id: uuid.UUID,
    body: ReportGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Generate a holdings report."""
    portfolio = await _get_portfolio(session, portfolio_id)
    return await _generate_report(session, portfolio, "HOLDINGS", body)


async def _build_report_data(
    session: AsyncSession, portfolio: Portfolio, report_type: str
) -> dict:
    """Assemble real report data via reporting_engine from actual DB state."""
    from src.engines import reporting_engine

    pos_rows = (
        await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id, Position.status == "OPEN"
            )
        )
    ).scalars().all()
    positions = [
        {
            "ticker": p.ticker,
            "shares": _opt_float(p.shares) or 0.0,
            "market_value": _opt_float(p.market_value) or 0.0,
            "weight": _opt_float(p.weight) or 0.0,
            "cost_basis": _opt_float(p.cost_basis_total) or 0.0,
            "unrealized_pnl": _opt_float(p.unrealized_pnl) or 0.0,
        }
        for p in pos_rows
    ]

    nav_snap = (
        await session.execute(
            select(NAVSnapshot)
            .where(NAVSnapshot.portfolio_id == portfolio.id)
            .order_by(NAVSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    nav = {
        "nav": _opt_float(nav_snap.nav) if nav_snap else 0.0,
        "market_value": _opt_float(nav_snap.market_value) if nav_snap else 0.0,
        "cash_balance": _opt_float(nav_snap.cash_balance) if nav_snap else 0.0,
        "unrealized_pnl": _opt_float(nav_snap.unrealized_pnl) if nav_snap else 0.0,
    }

    perf_snap = (
        await session.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.portfolio_id == portfolio.id)
            .order_by(PerformanceSnapshot.period_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    performance = None
    if perf_snap:
        performance = {
            "twr_return": _opt_float(perf_snap.twr_return) or 0.0,
            "annualized_return": _opt_float(perf_snap.twr_return) or 0.0,
            "benchmark_return": _opt_float(perf_snap.benchmark_return),
            "active_return": _opt_float(perf_snap.active_return),
            "volatility": _opt_float(perf_snap.volatility) or 0.0,
            "sharpe_ratio": _opt_float(perf_snap.sharpe_ratio) or 0.0,
            "sortino_ratio": _opt_float(perf_snap.sortino_ratio),
            "max_drawdown": _opt_float(perf_snap.max_drawdown) or 0.0,
            "beta": _opt_float(perf_snap.beta),
            "alpha": _opt_float(perf_snap.alpha),
            "tracking_error": _opt_float(perf_snap.tracking_error),
            "information_ratio": _opt_float(perf_snap.information_ratio),
            "positive_days": perf_snap.positive_days or 0,
            "negative_days": perf_snap.negative_days or 0,
            "best_day": _opt_float(perf_snap.best_day) or 0.0,
            "worst_day": _opt_float(perf_snap.worst_day) or 0.0,
        }

    if report_type == "SUMMARY":
        portfolio_dict = {
            "id": str(portfolio.id),
            "name": portfolio.portfolio_name,
            "inception_date": portfolio.inception_date.isoformat()
            if portfolio.inception_date else "",
            "strategy": portfolio.portfolio_type or "",
        }
        return reporting_engine.build_portfolio_summary_report(
            portfolio_dict, positions, nav, performance
        )

    attr = (
        await session.execute(
            select(AttributionResult)
            .where(AttributionResult.portfolio_id == portfolio.id)
            .order_by(AttributionResult.period_end.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if report_type == "PERFORMANCE":
        attribution = None
        if attr is not None:
            attribution = {
                "total_allocation": _opt_float(attr.total_allocation) or 0.0,
                "total_selection": _opt_float(attr.total_selection) or 0.0,
                "total_interaction": _opt_float(attr.total_interaction) or 0.0,
            }
        return reporting_engine.build_performance_report(
            performance or {}, attribution=attribution, benchmark_name=portfolio.benchmark_id
        )

    if report_type == "ATTRIBUTION":
        if attr is None:
            return reporting_engine.build_attribution_report()
        sector_detail = attr.sector_detail if isinstance(attr.sector_detail, list) else []
        factor_detail = attr.factor_detail if isinstance(attr.factor_detail, list) else []
        security_detail = [
            s for s in (attr.security_detail if isinstance(attr.security_detail, list) else [])
            if isinstance(s, dict)
        ]
        sorted_sec = sorted(
            security_detail, key=lambda x: x.get("contribution", 0.0), reverse=True
        )
        brinson = {
            "total_allocation": _opt_float(attr.total_allocation) or 0.0,
            "total_selection": _opt_float(attr.total_selection) or 0.0,
            "total_interaction": _opt_float(attr.total_interaction) or 0.0,
            "residual": _opt_float(attr.residual) or 0.0,
            "sector_detail": sector_detail,
        }
        factor = {"factors": factor_detail}
        contributors = {
            "top": sorted_sec[:5],
            "bottom": sorted_sec[-5:] if len(sorted_sec) >= 5 else sorted_sec,
        }
        return reporting_engine.build_attribution_report(
            brinson=brinson, factor=factor, contributors=contributors
        )

    # HOLDINGS
    return reporting_engine.build_holdings_report(positions)


async def _generate_report(
    session: AsyncSession,
    portfolio: Portfolio,
    report_type: str,
    body: ReportGenerateRequest | None,
) -> ReportResponse:
    """Internal helper to create a ReportRequest record."""
    fmt = body.format if body else "json"
    result_data = await _build_report_data(session, portfolio, report_type)
    report = ReportRequest(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        report_type=report_type,
        format=fmt,
        period_start=body.period_start if body else None,
        period_end=body.period_end if body else None,
        parameters=None,
        status="COMPLETED",
        result_data=result_data,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    return ReportResponse(
        report_id=report.id,
        portfolio_id=report.portfolio_id,
        report_type=report.report_type,
        format=report.format,
        status=report.status,
        data=report.result_data,
    )


# ══════════════════════════════════════════════════════════════════════
# Exports
# ══════════════════════════════════════════════════════════════════════


@router.get("/portfolios/{portfolio_id}/export/holdings")
async def export_holdings(
    portfolio_id: uuid.UUID,
    format: str = Query(default="csv"),
    session: AsyncSession = Depends(get_session),
):
    """Export holdings as CSV."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(Position)
        .where(Position.portfolio_id == portfolio_id, Position.status == "OPEN")
        .order_by(Position.ticker)
    )
    rows = result.scalars().all()

    csv_content = _rows_to_csv(
        ["ticker", "shares", "cost_basis_per_share", "cost_basis_total", "market_value"],
        [
            [
                pos.ticker, _opt_float(pos.shares),
                _opt_float(pos.cost_basis_per_share), _opt_float(pos.cost_basis_total),
                _opt_float(pos.market_value),
            ]
            for pos in rows
        ],
    )
    return PlainTextResponse(content=csv_content, media_type="text/csv")


@router.get("/portfolios/{portfolio_id}/export/transactions")
async def export_transactions(
    portfolio_id: uuid.UUID,
    format: str = Query(default="csv"),
    session: AsyncSession = Depends(get_session),
):
    """Export transactions as CSV."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(Transaction)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.scalars().all()

    csv_content = _rows_to_csv(
        ["date", "ticker", "type", "shares", "price", "gross", "commission", "net", "cash_impact"],
        [
            [
                t.transaction_date, t.ticker, t.transaction_type,
                _opt_float(t.shares), _opt_float(t.price_per_share),
                _opt_float(t.gross_amount), _opt_float(t.commission),
                _opt_float(t.net_amount), _opt_float(t.cash_impact),
            ]
            for t in rows
        ],
    )
    return PlainTextResponse(content=csv_content, media_type="text/csv")


@router.get("/portfolios/{portfolio_id}/export/nav")
async def export_nav(
    portfolio_id: uuid.UUID,
    format: str = Query(default="csv"),
    session: AsyncSession = Depends(get_session),
):
    """Export NAV history as CSV."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(NAVSnapshot)
        .where(NAVSnapshot.portfolio_id == portfolio_id)
        .order_by(NAVSnapshot.snapshot_date.asc())
    )
    rows = result.scalars().all()

    csv_content = _rows_to_csv(
        ["date", "nav", "market_value", "cash_balance", "daily_return", "cumulative_return"],
        [
            [
                snap.snapshot_date, _opt_float(snap.nav),
                _opt_float(snap.market_value), _opt_float(snap.cash_balance),
                _opt_float(snap.daily_return), _opt_float(snap.cumulative_return),
            ]
            for snap in rows
        ],
    )
    return PlainTextResponse(content=csv_content, media_type="text/csv")


@router.get("/portfolios/{portfolio_id}/export/returns")
async def export_returns(
    portfolio_id: uuid.UUID,
    format: str = Query(default="csv"),
    session: AsyncSession = Depends(get_session),
):
    """Export return series as CSV."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.portfolio_id == portfolio_id)
        .order_by(PerformanceSnapshot.period_end.asc())
    )
    rows = result.scalars().all()

    csv_content = _rows_to_csv(
        ["period_end", "period_type", "twr_return", "benchmark_return", "active_return"],
        [
            [
                snap.period_end, snap.period_type,
                _opt_float(snap.twr_return), _opt_float(snap.benchmark_return),
                _opt_float(snap.active_return),
            ]
            for snap in rows
        ],
    )
    return PlainTextResponse(content=csv_content, media_type="text/csv")


# ── JSONB parsers ────────────────────────────────────────────────────


def _parse_sector_detail(data: dict | list | None) -> list[SectorAttributionEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("sectors", [])
    return [
        SectorAttributionEntry(
            sector=item.get("sector", "Unknown"),
            portfolio_weight=item.get("portfolio_weight", 0.0),
            benchmark_weight=item.get("benchmark_weight", 0.0),
            portfolio_return=item.get("portfolio_return", 0.0),
            benchmark_return=item.get("benchmark_return", 0.0),
            allocation_effect=item.get("allocation_effect", 0.0),
            selection_effect=item.get("selection_effect", 0.0),
            interaction_effect=item.get("interaction_effect", 0.0),
            total_effect=item.get("total_effect", 0.0),
        )
        for item in items
        if isinstance(item, dict)
    ]


def _parse_security_detail(data: dict | list | None) -> list[SecurityContributionEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("securities", [])
    return [
        SecurityContributionEntry(
            ticker=item.get("ticker", "N/A"),
            weight=item.get("weight", 0.0),
            return_value=item.get("return", item.get("return_value", 0.0)),
            contribution=item.get("contribution", 0.0),
        )
        for item in items
        if isinstance(item, dict)
    ]


def _parse_factor_detail(data: dict | list | None) -> list[FactorAttributionEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("factors", [])
    return [
        FactorAttributionEntry(
            factor=item.get("factor", "Unknown"),
            portfolio_exposure=item.get("portfolio_exposure", 0.0),
            benchmark_exposure=item.get("benchmark_exposure", 0.0),
            factor_return=item.get("factor_return", 0.0),
            contribution=item.get("contribution", 0.0),
        )
        for item in items
        if isinstance(item, dict)
    ]
