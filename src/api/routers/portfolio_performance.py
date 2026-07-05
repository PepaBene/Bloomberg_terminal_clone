"""Portfolio Performance & Attribution API endpoints (Pillar 4 Phase 2)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.models.portfolio import Portfolio
from src.models.position import Position
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

        # Get latest performance snapshot
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


async def _generate_report(
    session: AsyncSession,
    portfolio: Portfolio,
    report_type: str,
    body: ReportGenerateRequest | None,
) -> ReportResponse:
    """Internal helper to create a ReportRequest record."""
    fmt = body.format if body else "json"
    report = ReportRequest(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        report_type=report_type,
        format=fmt,
        period_start=body.period_start if body else None,
        period_end=body.period_end if body else None,
        parameters=None,
        status="COMPLETED",
        result_data={"report_type": report_type, "portfolio_name": portfolio.portfolio_name},
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

    lines = ["ticker,shares,cost_basis_per_share,cost_basis_total,market_value"]
    for pos in rows:
        lines.append(
            f"{pos.ticker},{_opt_float(pos.shares)},"
            f"{_opt_float(pos.cost_basis_per_share)},{_opt_float(pos.cost_basis_total)},"
            f"{_opt_float(pos.market_value)}"
        )
    csv_content = "\n".join(lines)
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

    lines = ["date,ticker,type,shares,price,gross,commission,net,cash_impact"]
    for t in rows:
        lines.append(
            f"{t.transaction_date},{t.ticker},{t.transaction_type},"
            f"{_opt_float(t.shares)},{_opt_float(t.price_per_share)},"
            f"{_opt_float(t.gross_amount)},{_opt_float(t.commission)},"
            f"{_opt_float(t.net_amount)},{_opt_float(t.cash_impact)}"
        )
    csv_content = "\n".join(lines)
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

    lines = ["date,nav,market_value,cash_balance,daily_return,cumulative_return"]
    for snap in rows:
        lines.append(
            f"{snap.snapshot_date},{_opt_float(snap.nav)},"
            f"{_opt_float(snap.market_value)},{_opt_float(snap.cash_balance)},"
            f"{_opt_float(snap.daily_return)},{_opt_float(snap.cumulative_return)}"
        )
    csv_content = "\n".join(lines)
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

    lines = ["period_end,period_type,twr_return,benchmark_return,active_return"]
    for snap in rows:
        lines.append(
            f"{snap.period_end},{snap.period_type},"
            f"{_opt_float(snap.twr_return)},{_opt_float(snap.benchmark_return)},"
            f"{_opt_float(snap.active_return)}"
        )
    csv_content = "\n".join(lines)
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
    ]
