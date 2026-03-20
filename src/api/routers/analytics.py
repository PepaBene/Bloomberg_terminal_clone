"""Pillar 2: Analytics Engine API (Spec §14).

All analytics endpoints live under ``/v2/analytics/`` and return the
standard :class:`AnalyticsResponse` envelope.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.analytics import (
    AnalyticsResult,
    CalculationLineage,
    CompositeScore,
    CompsResult,
    DCFResult,
    DuPontDecomposition,
    MultipleTimeSeries,
    WACCResult,
)
from src.models.security import Security
from src.schemas.analytics import (
    AllCompositeScoresResponse,
    AllScoresResponse,
    AltmanResponse,
    AnalyticsEnvelope,
    AnalyticsMeta,
    AnalyticsResponse,
    BeneishResponse,
    BulkRatioRequest,
    CompositeScoreResponse,
    CompsResponse,
    DCFRequest,
    DCFResponse,
    DuPontHistoryResponse,
    DuPontResponse,
    FootballFieldResponse,
    IndustryKPIResponse,
    LineageHistoryResponse,
    LineageResponse,
    MetricComparisonResponse,
    MetricValue,
    MultipleHistoryPoint,
    MultipleHistoryResponse,
    MultiplesResponse,
    PeerComparisonResponse,
    PeerGroupResponse,
    PeerMemberResponse,
    PercentileRankResponse,
    PiotroskiResponse,
    RatioHistoryPoint,
    RatioHistoryResponse,
    RatiosByCategory,
    ScoreHistoryPoint,
    ScoreHistoryResponse,
    TrendMetric,
    TrendResponse,
    TTMResponse,
    WACCComponentsResponse,
    WACCResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_security(session: AsyncSession, security_id: uuid.UUID) -> Security:
    """Fetch a security or 404."""
    result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    sec = result.scalar_one_or_none()
    if sec is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return sec


def _results_to_category_dict(
    results: list[AnalyticsResult],
) -> dict[str, dict[str, float | None]]:
    """Group AnalyticsResult rows by category → {metric_name: value}."""
    cats: dict[str, dict[str, float | None]] = {}
    for r in results:
        cat_key = (r.metric_category or "OTHER").lower()
        cats.setdefault(cat_key, {})[r.metric_name] = float(r.value) if r.value is not None else None
    return cats


def _build_meta(engine: str, start: float, cache_hit: bool = False) -> AnalyticsMeta:
    return AnalyticsMeta(
        request_id=str(uuid.uuid4()),
        engine=engine,
        processing_time_ms=int((time.perf_counter() - start) * 1000),
        cache_hit=cache_hit,
    )


# ---------------------------------------------------------------------------
# Ratios (E1)
# ---------------------------------------------------------------------------

@router.get("/ratios/{security_id}", response_model=RatiosByCategory)
async def get_all_ratios(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """All ratios grouped by category for a security."""
    start = time.perf_counter()
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E1",
        )
        .order_by(AnalyticsResult.as_of_date.desc())
    )
    rows = result.scalars().all()
    cats = _results_to_category_dict(rows)

    return RatiosByCategory(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        ticker=getattr(sec, "ticker", None),
        as_of_date=rows[0].as_of_date if rows else None,
        profitability=cats.get("profitability", {}),
        leverage=cats.get("leverage", {}),
        efficiency=cats.get("efficiency", {}),
        growth=cats.get("growth", {}),
        valuation=cats.get("valuation", {}),
        per_share=cats.get("per_share", {}),
        cash_flow=cats.get("cash_flow", {}),
        capital_allocation=cats.get("capital_allocation", {}),
        dividend=cats.get("dividend", {}),
    )


@router.get("/ratios/{security_id}/vs-peers", response_model=PeerComparisonResponse)
async def get_ratios_vs_peers(
    security_id: uuid.UUID,
    method: str = Query(default="GICS_SUB_INDUSTRY", description="Peer selection method"),
    session: AsyncSession = Depends(get_session),
):
    """Compare company ratios against auto-selected peer group."""
    sec = await _resolve_security(session, security_id)

    try:
        from src.engines.peer_service import PeerService
        svc = PeerService()
        comparison = await svc.compare_vs_peers(session, security_id)
    except Exception as exc:
        logger.warning("Peer comparison failed: %s", exc)
        return PeerComparisonResponse(
            subject_security_id=security_id,
            subject_ticker=getattr(sec, "ticker", None),
        )

    return PeerComparisonResponse(
        subject_security_id=security_id,
        subject_ticker=getattr(sec, "ticker", None),
        peer_count=len(comparison.peer_group.peers) if comparison.peer_group else 0,
        as_of_date=comparison.as_of_date,
        comparisons=[
            MetricComparisonResponse(
                metric_name=c.metric_name,
                subject_value=c.subject_value,
                peer_mean=c.peer_mean,
                peer_median=c.peer_median,
                peer_min=c.peer_min,
                peer_max=c.peer_max,
                peer_std=c.peer_std,
                percentile=c.percentile,
                premium_discount=c.premium_discount,
            )
            for c in comparison.comparisons
        ],
    )


@router.get("/ratios/{security_id}/percentile", response_model=PercentileRankResponse)
async def get_percentile_ranks(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Percentile rank within GICS peer group for key metrics."""
    sec = await _resolve_security(session, security_id)

    try:
        from src.engines.peer_service import PeerService
        svc = PeerService()
        ranks = await svc.get_percentile_ranks(session, security_id)
    except Exception as exc:
        logger.warning("Percentile ranking failed: %s", exc)
        ranks = {}

    return PercentileRankResponse(
        security_id=security_id,
        ticker=getattr(sec, "ticker", None),
        percentiles=ranks,
    )


@router.get("/ratios/{security_id}/{category}", response_model=dict)
async def get_ratios_by_category(
    security_id: uuid.UUID,
    category: str,
    session: AsyncSession = Depends(get_session),
):
    """Ratios for a specific category (profitability, leverage, etc.)."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_category == category.upper(),
        )
        .order_by(AnalyticsResult.as_of_date.desc())
    )
    rows = result.scalars().all()
    return {r.metric_name: float(r.value) if r.value is not None else None for r in rows}


@router.get("/ratios/{security_id}/history", response_model=RatioHistoryResponse)
async def get_ratio_history(
    security_id: uuid.UUID,
    ratio: str = Query(..., description="Ratio name, e.g. 'gross_margin'"),
    periods: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Historical time series for a specific ratio."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.metric_name == ratio,
        )
        .order_by(AnalyticsResult.period_end_date.desc())
        .limit(periods)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No history found for ratio '{ratio}'")

    return RatioHistoryResponse(
        security_id=security_id,
        metric_name=ratio,
        metric_category=rows[0].metric_category,
        data_points=[
            RatioHistoryPoint(
                period=r.period,
                period_end_date=r.period_end_date,
                value=float(r.value) if r.value is not None else None,
                quality=r.data_quality,
            )
            for r in rows
        ],
    )


@router.post("/ratios/bulk", response_model=dict)
async def get_bulk_ratios(
    request: BulkRatioRequest,
    session: AsyncSession = Depends(get_session),
):
    """Ratios for multiple securities."""
    query = select(AnalyticsResult).where(
        AnalyticsResult.security_id.in_(request.security_ids),
        AnalyticsResult.engine_id == "E1",
    )
    if request.metrics:
        query = query.where(AnalyticsResult.metric_name.in_(request.metrics))
    if request.categories:
        query = query.where(AnalyticsResult.metric_category.in_([c.upper() for c in request.categories]))

    result = await session.execute(query)
    rows = result.scalars().all()

    # Group by security_id
    out: dict[str, dict[str, float | None]] = {}
    for r in rows:
        sid = str(r.security_id)
        out.setdefault(sid, {})[r.metric_name] = float(r.value) if r.value is not None else None
    return out


# ---------------------------------------------------------------------------
# DuPont (E1)
# ---------------------------------------------------------------------------

@router.get("/dupont/{security_id}", response_model=list[DuPontResponse])
async def get_dupont(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Latest DuPont decomposition (both 3-factor and 5-factor)."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(DuPontDecomposition)
        .where(DuPontDecomposition.entity_id == sec.issuer_entity_id)
        .order_by(DuPontDecomposition.period.desc())
        .limit(2)  # latest 3-factor + 5-factor
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No DuPont data available")
    return [DuPontResponse.model_validate(r) for r in rows]


@router.get("/dupont/{security_id}/history", response_model=DuPontHistoryResponse)
async def get_dupont_history(
    security_id: uuid.UUID,
    model_type: str = Query(default="THREE_FACTOR"),
    periods: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """DuPont decomposition history."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(DuPontDecomposition)
        .where(
            DuPontDecomposition.entity_id == sec.issuer_entity_id,
            DuPontDecomposition.model_type == model_type.upper(),
        )
        .order_by(DuPontDecomposition.period.desc())
        .limit(periods)
    )
    rows = result.scalars().all()
    return DuPontHistoryResponse(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        decompositions=[DuPontResponse.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# TTM (E1)
# ---------------------------------------------------------------------------

@router.get("/ttm/{security_id}", response_model=TTMResponse)
async def get_ttm(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Trailing twelve month financial metrics."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.period == "TTM",
        )
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No TTM data available")

    return TTMResponse(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        as_of_date=rows[0].as_of_date if rows else None,
        metrics={r.metric_name: float(r.value) if r.value is not None else None for r in rows},
        quarters_used=4,
        data_quality=rows[0].data_quality if rows else "INSUFFICIENT_DATA",
    )


# ---------------------------------------------------------------------------
# Multiples (E2)
# ---------------------------------------------------------------------------

@router.get("/multiples/{security_id}", response_model=MultiplesResponse)
async def get_multiples(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Current valuation multiples."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E2",
            AnalyticsResult.metric_category == "VALUATION",
        )
        .order_by(AnalyticsResult.as_of_date.desc())
    )
    rows = result.scalars().all()

    return MultiplesResponse(
        security_id=security_id,
        ticker=getattr(sec, "ticker", None),
        as_of_date=rows[0].as_of_date if rows else None,
        multiples={r.metric_name: float(r.value) if r.value is not None else None for r in rows},
    )


@router.get("/multiples/{security_id}/history", response_model=MultipleHistoryResponse)
async def get_multiple_history(
    security_id: uuid.UUID,
    multiple: str = Query(default="PE_TRAILING", description="Multiple type"),
    periods: int = Query(default=252, ge=1, le=2520),
    session: AsyncSession = Depends(get_session),
):
    """Historical time series for a valuation multiple."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(MultipleTimeSeries)
        .where(
            MultipleTimeSeries.security_id == security_id,
            MultipleTimeSeries.multiple_type == multiple.upper(),
        )
        .order_by(MultipleTimeSeries.calculation_date.desc())
        .limit(periods)
    )
    rows = result.scalars().all()

    return MultipleHistoryResponse(
        security_id=security_id,
        multiple_type=multiple.upper(),
        data_points=[
            MultipleHistoryPoint(
                calculation_date=r.calculation_date,
                value=float(r.value) if r.value is not None else None,
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# WACC (E2)
# ---------------------------------------------------------------------------

@router.get("/wacc/{security_id}", response_model=WACCResponse)
async def get_wacc(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Latest WACC with component breakdown."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(WACCResult)
        .where(WACCResult.entity_id == sec.issuer_entity_id)
        .order_by(WACCResult.calculation_date.desc())
        .limit(1)
    )
    wacc = result.scalar_one_or_none()
    if wacc is None:
        raise HTTPException(status_code=404, detail="No WACC data available")
    return WACCResponse.model_validate(wacc)


@router.get("/wacc/{security_id}/history", response_model=list[WACCResponse])
async def get_wacc_history(
    security_id: uuid.UUID,
    periods: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """WACC history over time."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(WACCResult)
        .where(WACCResult.entity_id == sec.issuer_entity_id)
        .order_by(WACCResult.calculation_date.desc())
        .limit(periods)
    )
    rows = result.scalars().all()
    return [WACCResponse.model_validate(r) for r in rows]


@router.get("/wacc/{security_id}/components", response_model=WACCComponentsResponse)
async def get_wacc_components(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Detailed WACC component breakdown."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(WACCResult)
        .where(WACCResult.entity_id == sec.issuer_entity_id)
        .order_by(WACCResult.calculation_date.desc())
        .limit(1)
    )
    wacc = result.scalar_one_or_none()
    if wacc is None:
        raise HTTPException(status_code=404, detail="No WACC data available")

    return WACCComponentsResponse(
        entity_id=wacc.entity_id,
        calculation_date=wacc.calculation_date,
        risk_free_rate=float(wacc.risk_free_rate) if wacc.risk_free_rate else None,
        equity_risk_premium=float(wacc.equity_risk_premium) if wacc.equity_risk_premium else None,
        beta=float(wacc.beta) if wacc.beta else None,
        size_premium=float(wacc.size_premium) if wacc.size_premium else None,
        country_premium=float(wacc.country_premium) if wacc.country_premium else None,
        cost_of_equity=float(wacc.cost_of_equity) if wacc.cost_of_equity else None,
        cost_of_debt_pretax=float(wacc.cost_of_debt_pretax) if wacc.cost_of_debt_pretax else None,
        effective_tax_rate=float(wacc.effective_tax_rate) if wacc.effective_tax_rate else None,
        cost_of_debt_aftertax=float(wacc.cost_of_debt_aftertax) if wacc.cost_of_debt_aftertax else None,
        debt_weight=float(wacc.debt_weight) if wacc.debt_weight else None,
        equity_weight=float(wacc.equity_weight) if wacc.equity_weight else None,
        wacc=float(wacc.wacc) if wacc.wacc else None,
        market_cap=float(wacc.market_cap) if wacc.market_cap else None,
        total_debt=float(wacc.total_debt) if wacc.total_debt else None,
    )


# ---------------------------------------------------------------------------
# Audit / Lineage (Spec §15)
# ---------------------------------------------------------------------------

@router.get("/audit/{security_id}/{metric_name}", response_model=LineageResponse)
async def get_lineage(
    security_id: uuid.UUID,
    metric_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Calculation lineage for a specific metric."""
    result = await session.execute(
        select(CalculationLineage)
        .where(
            CalculationLineage.security_id == security_id,
            CalculationLineage.output_metric == metric_name,
        )
        .order_by(CalculationLineage.calculated_at.desc())
        .limit(1)
    )
    lineage = result.scalar_one_or_none()
    if lineage is None:
        raise HTTPException(status_code=404, detail=f"No lineage found for metric '{metric_name}'")
    return LineageResponse.model_validate(lineage)


@router.get("/audit/{security_id}/{metric_name}/history", response_model=LineageHistoryResponse)
async def get_lineage_history(
    security_id: uuid.UUID,
    metric_name: str,
    periods: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Historical lineage entries for a metric."""
    result = await session.execute(
        select(CalculationLineage)
        .where(
            CalculationLineage.security_id == security_id,
            CalculationLineage.output_metric == metric_name,
        )
        .order_by(CalculationLineage.calculated_at.desc())
        .limit(periods)
    )
    rows = result.scalars().all()
    return LineageHistoryResponse(
        security_id=security_id,
        metric_name=metric_name,
        entries=[LineageResponse.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Trend Analysis (E1 — Part 1B)
# ---------------------------------------------------------------------------

@router.get("/trends/{security_id}", response_model=TrendResponse)
async def get_trends(
    security_id: uuid.UUID,
    ratio: str | None = Query(default=None, description="Filter to a specific ratio"),
    session: AsyncSession = Depends(get_session),
):
    """Trend analysis for ratio time series — direction, momentum, consistency, mean reversion."""
    sec = await _resolve_security(session, security_id)

    query = select(AnalyticsResult).where(
        AnalyticsResult.security_id == security_id,
        AnalyticsResult.engine_id == "E1",
        AnalyticsResult.metric_category == "TREND",
    )
    result = await session.execute(query)
    rows = result.scalars().all()

    # Group by base ratio name (strip suffixes like _trend_1y, _momentum, etc.)
    from collections import defaultdict

    # Separate containers for numeric fields vs string label fields
    STRING_SUFFIXES = ("_trend_1y", "_trend_3y", "_trend_5y", "_consistency", "_mean_reversion_signal")
    NUMERIC_SUFFIXES = (
        "_change_1y", "_change_3y", "_change_5y",
        "_momentum", "_acceleration",
        "_std_5y", "_cov_5y",
        "_zscore_5y", "_current_value",
    )
    ALL_SUFFIXES = STRING_SUFFIXES + NUMERIC_SUFFIXES

    by_ratio: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        name = r.metric_name
        for suffix in ALL_SUFFIXES:
            if name.endswith(suffix):
                base = name[: -len(suffix)]
                field_key = suffix[1:]  # strip leading underscore
                if suffix in STRING_SUFFIXES:
                    # String-valued: get label from inputs
                    label = None
                    if r.inputs and isinstance(r.inputs, list):
                        label = next((inp.get("value") for inp in r.inputs if inp.get("name") == "label"), None)
                    by_ratio[base][field_key] = label
                else:
                    by_ratio[base][field_key] = float(r.value) if r.value is not None else None
                break

    # Filter if specific ratio requested
    if ratio:
        by_ratio = {k: v for k, v in by_ratio.items() if k == ratio}

    trends = []
    for rname, fields in sorted(by_ratio.items()):
        trends.append(TrendMetric(
            ratio_name=rname,
            current_value=fields.get("current_value"),
            trend_1y=fields.get("trend_1y"),
            change_1y=fields.get("change_1y"),
            trend_3y=fields.get("trend_3y"),
            change_3y=fields.get("change_3y"),
            trend_5y=fields.get("trend_5y"),
            change_5y=fields.get("change_5y"),
            momentum=fields.get("momentum"),
            acceleration=fields.get("acceleration"),
            std_5y=fields.get("std_5y"),
            cov_5y=fields.get("cov_5y"),
            consistency=fields.get("consistency"),
            zscore_5y=fields.get("zscore_5y"),
            mean_reversion_signal=fields.get("mean_reversion_signal"),
        ))

    return TrendResponse(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        ticker=getattr(sec, "ticker", None),
        as_of_date=rows[0].as_of_date if rows else None,
        trends=trends,
    )


# ---------------------------------------------------------------------------
# Industry KPIs (E1 — Part 1B)
# ---------------------------------------------------------------------------

@router.get("/kpis/{security_id}", response_model=IndustryKPIResponse)
async def get_industry_kpis(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Industry-specific KPIs based on GICS classification."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_category == "INDUSTRY_KPI",
        )
    )
    rows = result.scalars().all()

    kpis = {r.metric_name: float(r.value) if r.value is not None else None for r in rows}

    # Extract kpi_set_applied from first row's inputs if available
    kpi_set = None
    gics_sector = None
    gics_industry = None
    if rows and rows[0].inputs and isinstance(rows[0].inputs, list):
        for inp in rows[0].inputs:
            if inp.get("name") == "kpi_set_applied":
                kpi_set = inp.get("value")
            if inp.get("name") == "gics_sector":
                gics_sector = inp.get("value")
            if inp.get("name") == "gics_industry":
                gics_industry = inp.get("value")

    return IndustryKPIResponse(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        ticker=getattr(sec, "ticker", None),
        gics_sector=gics_sector,
        gics_industry=gics_industry,
        kpi_set_applied=kpi_set,
        kpis=kpis,
    )


@router.get("/kpis/{security_id}/history", response_model=dict)
async def get_industry_kpis_history(
    security_id: uuid.UUID,
    kpi: str = Query(..., description="KPI name, e.g. 'rule_of_40'"),
    periods: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Historical values for a specific industry KPI."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_category == "INDUSTRY_KPI",
            AnalyticsResult.metric_name == kpi,
        ).order_by(AnalyticsResult.period_end_date.desc()).limit(periods)
    )
    rows = result.scalars().all()
    return {
        "security_id": str(security_id),
        "kpi": kpi,
        "data_points": [
            {"period": r.period, "value": float(r.value) if r.value is not None else None}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Peer Group (Part 1B)
# ---------------------------------------------------------------------------

@router.get("/peers/{security_id}", response_model=PeerGroupResponse)
async def get_peer_group(
    security_id: uuid.UUID,
    method: str = Query(default="GICS_SUB_INDUSTRY"),
    max_peers: int = Query(default=15, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Auto-generated peer group for a security."""
    sec = await _resolve_security(session, security_id)

    try:
        from src.engines.peer_service import PeerService
        svc = PeerService()
        pg = await svc.get_peers(session, security_id, method=method, max_peers=max_peers)
    except Exception as exc:
        logger.warning("Peer group generation failed: %s", exc)
        return PeerGroupResponse(
            subject_security_id=security_id,
            subject_ticker=getattr(sec, "ticker", None),
        )

    return PeerGroupResponse(
        subject_security_id=security_id,
        subject_ticker=getattr(sec, "ticker", None),
        method=pg.method,
        peer_count=len(pg.peers),
        peers=[
            PeerMemberResponse(
                security_id=p.security_id,
                entity_id=p.entity_id,
                ticker=p.ticker,
                name=p.name,
                gics_sub_industry=p.gics_sub_industry,
                market_cap=p.market_cap,
                similarity_score=p.similarity_score,
            )
            for p in pg.peers
        ],
    )


# ---------------------------------------------------------------------------
# Quality & Scoring (E3)
# ---------------------------------------------------------------------------

def _scores_from_results(
    rows: list[AnalyticsResult],
) -> dict[str, float | None]:
    """Extract E3 quality metrics by name from AnalyticsResult rows."""
    return {r.metric_name: float(r.value) if r.value is not None else None for r in rows}


def _score_str(rows: list[AnalyticsResult], name: str) -> str | None:
    """Extract a string-valued classification from inputs."""
    for r in rows:
        if r.metric_name == name:
            if r.inputs and isinstance(r.inputs, list):
                for inp in r.inputs:
                    if inp.get("name") == "label":
                        return inp.get("value")
            # fallback: treat small integers stored in value as score
            return None
    return None


def _build_piotroski(
    security_id: uuid.UUID, entity_id: uuid.UUID | None, ticker: str | None,
    rows: list[AnalyticsResult],
) -> PiotroskiResponse:
    m = _scores_from_results(rows)
    return PiotroskiResponse(
        security_id=security_id,
        entity_id=entity_id,
        ticker=ticker,
        as_of_date=rows[0].as_of_date if rows else None,
        f_score=int(m["piotroski_f_score"]) if m.get("piotroski_f_score") is not None else None,
        zone=_score_str(rows, "piotroski_zone"),
        f1_positive_income=int(m.get("piotroski_f1_positive_income") or 0) if "piotroski_f1_positive_income" in m else None,
        f2_positive_ocf=int(m.get("piotroski_f2_positive_ocf") or 0) if "piotroski_f2_positive_ocf" in m else None,
        f3_improving_roa=int(m.get("piotroski_f3_improving_roa") or 0) if "piotroski_f3_improving_roa" in m else None,
        f4_earnings_quality=int(m.get("piotroski_f4_earnings_quality") or 0) if "piotroski_f4_earnings_quality" in m else None,
        f5_deleveraging=int(m.get("piotroski_f5_deleveraging") or 0) if "piotroski_f5_deleveraging" in m else None,
        f6_improving_liquidity=int(m.get("piotroski_f6_improving_liquidity") or 0) if "piotroski_f6_improving_liquidity" in m else None,
        f7_no_dilution=int(m.get("piotroski_f7_no_dilution") or 0) if "piotroski_f7_no_dilution" in m else None,
        f8_improving_gross_margin=int(m.get("piotroski_f8_improving_gross_margin") or 0) if "piotroski_f8_improving_gross_margin" in m else None,
        f9_improving_asset_turnover=int(m.get("piotroski_f9_improving_asset_turnover") or 0) if "piotroski_f9_improving_asset_turnover" in m else None,
        profitability_subscore=int(m.get("piotroski_profitability_subscore") or 0) if "piotroski_profitability_subscore" in m else None,
        data_quality=rows[0].data_quality if rows else "INSUFFICIENT_DATA",
    )


def _build_altman(
    security_id: uuid.UUID, entity_id: uuid.UUID | None, ticker: str | None,
    rows: list[AnalyticsResult],
) -> AltmanResponse:
    m = _scores_from_results(rows)
    return AltmanResponse(
        security_id=security_id,
        entity_id=entity_id,
        ticker=ticker,
        as_of_date=rows[0].as_of_date if rows else None,
        z_score=m.get("altman_z_score"),
        zone=_score_str(rows, "altman_zone"),
        model=_score_str(rows, "altman_model"),
        x1_wc_ta=m.get("altman_x1_wc_ta"),
        x2_re_ta=m.get("altman_x2_re_ta"),
        x3_ebit_ta=m.get("altman_x3_ebit_ta"),
        x4_equity_tl=m.get("altman_x4_mve_tl"),
        x5_sales_ta=m.get("altman_x5_sales_ta"),
        implied_pd=m.get("altman_implied_pd"),
        gics_sector=_score_str(rows, "altman_gics_sector"),
        data_quality=rows[0].data_quality if rows else "INSUFFICIENT_DATA",
    )


def _build_beneish(
    security_id: uuid.UUID, entity_id: uuid.UUID | None, ticker: str | None,
    rows: list[AnalyticsResult],
) -> BeneishResponse:
    m = _scores_from_results(rows)
    return BeneishResponse(
        security_id=security_id,
        entity_id=entity_id,
        ticker=ticker,
        as_of_date=rows[0].as_of_date if rows else None,
        m_score=m.get("beneish_m_score"),
        flag=_score_str(rows, "beneish_flag"),
        dsri=m.get("beneish_dsri"),
        gmi=m.get("beneish_gmi"),
        aqi=m.get("beneish_aqi"),
        sgi=m.get("beneish_sgi"),
        depi=m.get("beneish_depi"),
        sgai=m.get("beneish_sgai"),
        tata=m.get("beneish_tata"),
        lvgi=m.get("beneish_lvgi"),
        components_available=int(m["beneish_components_available"]) if m.get("beneish_components_available") is not None else None,
        data_quality=rows[0].data_quality if rows else "INSUFFICIENT_DATA",
    )


@router.get("/scores/{security_id}", response_model=AllScoresResponse)
async def get_all_scores(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """All quality scores (Piotroski, Altman, Beneish) for a security."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E3",
        )
    )
    rows = result.scalars().all()

    pio_rows = [r for r in rows if r.metric_name.startswith("piotroski_")]
    alt_rows = [r for r in rows if r.metric_name.startswith("altman_")]
    ben_rows = [r for r in rows if r.metric_name.startswith("beneish_")]

    entity_id = sec.issuer_entity_id
    ticker = getattr(sec, "ticker", None)

    return AllScoresResponse(
        security_id=security_id,
        entity_id=entity_id,
        ticker=ticker,
        as_of_date=rows[0].as_of_date if rows else None,
        piotroski=_build_piotroski(security_id, entity_id, ticker, pio_rows) if pio_rows else None,
        altman=_build_altman(security_id, entity_id, ticker, alt_rows) if alt_rows else None,
        beneish=_build_beneish(security_id, entity_id, ticker, ben_rows) if ben_rows else None,
    )


@router.get("/scores/{security_id}/piotroski", response_model=PiotroskiResponse)
async def get_piotroski(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Piotroski F-Score with full component breakdown."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E3",
            AnalyticsResult.metric_name.startswith("piotroski_"),
        )
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No Piotroski data available")

    return _build_piotroski(security_id, sec.issuer_entity_id, getattr(sec, "ticker", None), rows)


@router.get("/scores/{security_id}/altman", response_model=AltmanResponse)
async def get_altman(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Altman Z-Score with component breakdown."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E3",
            AnalyticsResult.metric_name.startswith("altman_"),
        )
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No Altman data available")

    return _build_altman(security_id, sec.issuer_entity_id, getattr(sec, "ticker", None), rows)


@router.get("/scores/{security_id}/beneish", response_model=BeneishResponse)
async def get_beneish(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Beneish M-Score with component breakdown."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.engine_id == "E3",
            AnalyticsResult.metric_name.startswith("beneish_"),
        )
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No Beneish data available")

    return _build_beneish(security_id, sec.issuer_entity_id, getattr(sec, "ticker", None), rows)


@router.get("/scores/{security_id}/history", response_model=ScoreHistoryResponse)
async def get_score_history(
    security_id: uuid.UUID,
    score_type: str = Query(default="piotroski", description="Score type: piotroski, altman, beneish"),
    periods: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Historical quality scores."""
    await _resolve_security(session, security_id)

    metric_name_map = {
        "piotroski": "piotroski_f_score",
        "altman": "altman_z_score",
        "beneish": "beneish_m_score",
    }
    metric_name = metric_name_map.get(score_type.lower())
    if not metric_name:
        raise HTTPException(status_code=400, detail=f"Unknown score type: {score_type}")

    result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.metric_name == metric_name,
        ).order_by(AnalyticsResult.period_end_date.desc()).limit(periods)
    )
    rows = result.scalars().all()

    # Also get zone/flag for each period
    zone_name_map = {
        "piotroski": "piotroski_zone",
        "altman": "altman_zone",
        "beneish": "beneish_flag",
    }
    zone_metric = zone_name_map.get(score_type.lower())
    zone_result = await session.execute(
        select(AnalyticsResult).where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.metric_name == zone_metric,
        ).order_by(AnalyticsResult.period_end_date.desc()).limit(periods)
    )
    zone_rows = {r.period: r for r in zone_result.scalars().all()}

    return ScoreHistoryResponse(
        security_id=security_id,
        score_type=score_type.lower(),
        data_points=[
            ScoreHistoryPoint(
                period=r.period,
                period_end_date=r.period_end_date,
                score=float(r.value) if r.value is not None else None,
                zone=_score_str([zone_rows[r.period]], zone_metric) if r.period in zone_rows else None,
                data_quality=r.data_quality,
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# DCF Valuation (E2 — Part 2)
# ---------------------------------------------------------------------------

@router.post("/dcf/{security_id}", response_model=DCFResponse)
async def run_dcf(
    security_id: uuid.UUID,
    request: DCFRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Run DCF with custom assumptions (or defaults)."""
    sec = await _resolve_security(session, security_id)

    try:
        from src.engines.e2_dcf import DCFEngine
        engine = DCFEngine()
        kwargs: dict[str, Any] = {"method": request.method if request else "FCFF"}
        if request and request.wacc_override is not None:
            kwargs["wacc_override"] = request.wacc_override
        if request:
            kwargs["assumptions"] = request.model_dump(exclude_none=True, exclude={"method", "wacc_override"})
        results = await engine.compute(session, security_id=security_id, **kwargs)
    except Exception as exc:
        logger.error("DCF computation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"DCF computation failed: {exc}")

    # Find persisted DCFResult
    result = await session.execute(
        select(DCFResult)
        .where(DCFResult.security_id == security_id)
        .order_by(DCFResult.calculation_date.desc())
        .limit(1)
    )
    dcf = result.scalar_one_or_none()
    if dcf is None:
        raise HTTPException(status_code=500, detail="DCF result not persisted")
    return DCFResponse.model_validate(dcf)


@router.get("/dcf/{security_id}/default", response_model=DCFResponse)
async def get_dcf_default(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get latest DCF valuation with default assumptions."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(DCFResult)
        .where(DCFResult.security_id == security_id)
        .order_by(DCFResult.calculation_date.desc())
        .limit(1)
    )
    dcf = result.scalar_one_or_none()
    if dcf is None:
        raise HTTPException(status_code=404, detail="No DCF data available — run POST /dcf/{id} first")
    return DCFResponse.model_validate(dcf)


# ---------------------------------------------------------------------------
# Comparable Analysis (E2 — Part 2)
# ---------------------------------------------------------------------------

@router.get("/comps/{security_id}", response_model=CompsResponse)
async def get_comps(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Comparable company analysis with peer multiples."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(CompsResult)
        .where(CompsResult.security_id == security_id)
        .order_by(CompsResult.calculation_date.desc())
        .limit(1)
    )
    comps = result.scalar_one_or_none()
    if comps is None:
        # Try computing on demand
        try:
            from src.engines.e2_comps import CompsEngine
            engine = CompsEngine()
            await engine.compute(session, security_id=security_id)
            result2 = await session.execute(
                select(CompsResult)
                .where(CompsResult.security_id == security_id)
                .order_by(CompsResult.calculation_date.desc())
                .limit(1)
            )
            comps = result2.scalar_one_or_none()
        except Exception as exc:
            logger.error("Comps computation failed: %s", exc)

    if comps is None:
        raise HTTPException(status_code=404, detail="No comparable analysis available")
    return CompsResponse.model_validate(comps)


@router.get("/comps/{security_id}/summary", response_model=dict)
async def get_comps_summary(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Quick implied value from comparable analysis."""
    await _resolve_security(session, security_id)

    result = await session.execute(
        select(CompsResult)
        .where(CompsResult.security_id == security_id)
        .order_by(CompsResult.calculation_date.desc())
        .limit(1)
    )
    comps = result.scalar_one_or_none()
    if comps is None:
        raise HTTPException(status_code=404, detail="No comparable analysis available")

    return {
        "security_id": str(security_id),
        "composite_implied_price": float(comps.composite_implied_price) if comps.composite_implied_price else None,
        "current_price": float(comps.current_price) if comps.current_price else None,
        "peer_count": comps.peer_count,
    }


# ---------------------------------------------------------------------------
# Football Field — Valuation Summary (E2 — Part 2)
# ---------------------------------------------------------------------------

@router.get("/valuation/{security_id}/summary", response_model=FootballFieldResponse)
async def get_football_field(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Combined valuation range from all methodologies."""
    sec = await _resolve_security(session, security_id)

    try:
        from src.engines.e2_football_field import FootballFieldEngine
        engine = FootballFieldEngine()
        results = await engine.compute(session, security_id=security_id)
    except Exception as exc:
        logger.error("Football field failed: %s", exc)
        results = []

    # Build response from EngineOutput list
    from src.schemas.analytics import ValuationMethodRange
    methods: dict[str, dict] = {}
    current_price = None
    consensus = None

    for r in results:
        if r.metric_name == "football_current_price":
            current_price = r.value
        elif r.metric_name == "football_consensus_view":
            consensus = r.data_quality
        elif r.metric_name.startswith("football_"):
            # Parse: football_{method}_{low|mid|high}
            parts = r.metric_name.replace("football_", "").rsplit("_", 1)
            if len(parts) == 2:
                method_name, bound = parts
                methods.setdefault(method_name, {"methodology": method_name})
                methods[method_name][bound] = r.value

    return FootballFieldResponse(
        security_id=security_id,
        ticker=getattr(sec, "ticker", None),
        current_price=current_price,
        methodologies=[
            ValuationMethodRange(**m) for m in methods.values()
        ],
        consensus_view=consensus,
    )


# ---------------------------------------------------------------------------
# Composite Quality Scores (E3 — Part 2)
# ---------------------------------------------------------------------------

@router.get("/scores/{security_id}/composites", response_model=AllCompositeScoresResponse)
async def get_composite_scores(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """All composite quality scores (earnings quality, financial strength, dividend safety, value trap)."""
    sec = await _resolve_security(session, security_id)

    result = await session.execute(
        select(CompositeScore)
        .where(CompositeScore.security_id == security_id)
        .order_by(CompositeScore.calculation_date.desc())
    )
    rows = result.scalars().all()

    # Group by score_type, keep latest of each
    by_type: dict[str, CompositeScore] = {}
    for r in rows:
        if r.score_type not in by_type:
            by_type[r.score_type] = r

    def _to_response(cs: CompositeScore | None) -> CompositeScoreResponse | None:
        if cs is None:
            return None
        return CompositeScoreResponse(
            score_type=cs.score_type,
            score_value=float(cs.score_value) if cs.score_value is not None else None,
            classification=cs.classification,
            components=cs.components if isinstance(cs.components, list) else [],
            data_quality=cs.data_quality,
        )

    return AllCompositeScoresResponse(
        security_id=security_id,
        entity_id=sec.issuer_entity_id,
        ticker=getattr(sec, "ticker", None),
        as_of_date=rows[0].calculation_date if rows else None,
        earnings_quality=_to_response(by_type.get("EARNINGS_QUALITY")),
        financial_strength=_to_response(by_type.get("FINANCIAL_STRENGTH")),
        dividend_safety=_to_response(by_type.get("DIVIDEND_SAFETY")),
        value_trap=_to_response(by_type.get("VALUE_TRAP")),
    )


@router.get("/scores/{security_id}/earnings-quality", response_model=CompositeScoreResponse)
async def get_earnings_quality(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Earnings quality composite score."""
    await _resolve_security(session, security_id)
    result = await session.execute(
        select(CompositeScore).where(
            CompositeScore.security_id == security_id,
            CompositeScore.score_type == "EARNINGS_QUALITY",
        ).order_by(CompositeScore.calculation_date.desc()).limit(1)
    )
    cs = result.scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="No earnings quality score available")
    return CompositeScoreResponse(
        score_type=cs.score_type,
        score_value=float(cs.score_value) if cs.score_value is not None else None,
        classification=cs.classification,
        components=cs.components if isinstance(cs.components, list) else [],
        data_quality=cs.data_quality,
    )


@router.get("/scores/{security_id}/financial-strength", response_model=CompositeScoreResponse)
async def get_financial_strength(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Financial strength composite score."""
    await _resolve_security(session, security_id)
    result = await session.execute(
        select(CompositeScore).where(
            CompositeScore.security_id == security_id,
            CompositeScore.score_type == "FINANCIAL_STRENGTH",
        ).order_by(CompositeScore.calculation_date.desc()).limit(1)
    )
    cs = result.scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="No financial strength score available")
    return CompositeScoreResponse(
        score_type=cs.score_type,
        score_value=float(cs.score_value) if cs.score_value is not None else None,
        classification=cs.classification,
        components=cs.components if isinstance(cs.components, list) else [],
        data_quality=cs.data_quality,
    )


@router.get("/scores/{security_id}/dividend-safety", response_model=CompositeScoreResponse)
async def get_dividend_safety(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Dividend safety assessment."""
    await _resolve_security(session, security_id)
    result = await session.execute(
        select(CompositeScore).where(
            CompositeScore.security_id == security_id,
            CompositeScore.score_type == "DIVIDEND_SAFETY",
        ).order_by(CompositeScore.calculation_date.desc()).limit(1)
    )
    cs = result.scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="No dividend safety score available")
    return CompositeScoreResponse(
        score_type=cs.score_type,
        score_value=float(cs.score_value) if cs.score_value is not None else None,
        classification=cs.classification,
        components=cs.components if isinstance(cs.components, list) else [],
        data_quality=cs.data_quality,
    )


@router.get("/scores/{security_id}/value-trap", response_model=CompositeScoreResponse)
async def get_value_trap(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Value trap risk assessment."""
    await _resolve_security(session, security_id)
    result = await session.execute(
        select(CompositeScore).where(
            CompositeScore.security_id == security_id,
            CompositeScore.score_type == "VALUE_TRAP",
        ).order_by(CompositeScore.calculation_date.desc()).limit(1)
    )
    cs = result.scalar_one_or_none()
    if cs is None:
        raise HTTPException(status_code=404, detail="No value trap score available")
    return CompositeScoreResponse(
        score_type=cs.score_type,
        score_value=float(cs.score_value) if cs.score_value is not None else None,
        classification=cs.classification,
        components=cs.components if isinstance(cs.components, list) else [],
        data_quality=cs.data_quality,
    )
