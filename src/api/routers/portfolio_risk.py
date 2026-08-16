"""Portfolio Risk Management API endpoints (Pillar 4 Phase 3)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import drift_engine, e2_wacc, portfolio_risk_engine, trade_list_engine, treasury_analytics
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.security import EODPrice, FixedIncomeDetails, Security
from src.models.portfolio_risk import (
    ConcentrationAnalysis,
    FactorExposureSnapshot,
    PortfolioVarSnapshot,
    PortfolioStressTestResult,
)
from src.models.compliance import ComplianceRule, ComplianceResult, DriftSnapshot
from src.schemas.portfolio_risk import (
    ConcentrationResponse,
    FactorExposureResponse,
    FactorHistoryEntry,
    RiskDashboardResponse,
    SectorConcentrationEntry,
    StressScenarioResponse,
    StressTestRequest,
    StressTestResponse,
    VaRDecompositionResponse,
    VaRResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from src.schemas.compliance_schema import (
    ComplianceResultResponse,
    ComplianceRuleCreateRequest,
    ComplianceRuleResponse,
    ComplianceRuleUpdateRequest,
    ComplianceSummaryResponse,
    PreTradeCheckRequest,
    PreTradeCheckResponse,
)
from src.schemas.drift_schema import (
    DriftResponse,
    PositionDriftEntry,
    RebalanceSuggestionResponse,
    SectorDriftEntry,
    TargetAllocationRequest,
)
from src.schemas.trade_list_schema import TradeListResponse, TradeListSummaryEntry, TradeOrderEntry

router = APIRouter(tags=["Portfolio Risk"])


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


# ══════════════════════════════════════════════════════════════════════
# Static route — MUST be before /{portfolio_id} routes
# ══════════════════════════════════════════════════════════════════════


AVAILABLE_SCENARIOS = [
    StressScenarioResponse(scenario_name="2008_GFC", scenario_type="HISTORICAL", description="2008 Global Financial Crisis"),
    StressScenarioResponse(scenario_name="2020_COVID", scenario_type="HISTORICAL", description="2020 COVID-19 crash"),
    StressScenarioResponse(scenario_name="2022_RATE_HIKE", scenario_type="HISTORICAL", description="2022 interest rate hiking cycle"),
    StressScenarioResponse(scenario_name="DOT_COM_BUST", scenario_type="HISTORICAL", description="2000 Dot-com bust"),
    StressScenarioResponse(scenario_name="EQUITY_MINUS_20", scenario_type="HYPOTHETICAL", description="Equity markets down 20%"),
    StressScenarioResponse(scenario_name="RATES_PLUS_200BP", scenario_type="HYPOTHETICAL", description="Interest rates +200bp"),
]


@router.get("/portfolios/risk/scenarios", response_model=list[StressScenarioResponse])
async def list_stress_scenarios():
    """List available stress-test scenarios."""
    return AVAILABLE_SCENARIOS


# ══════════════════════════════════════════════════════════════════════
# Risk Dashboard
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/risk",
    response_model=RiskDashboardResponse,
)
async def get_risk_dashboard(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get full risk dashboard: VaR + concentration + factors."""
    await _get_portfolio(session, portfolio_id)

    # VaR
    var_result = await session.execute(
        select(PortfolioVarSnapshot)
        .where(PortfolioVarSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioVarSnapshot.snapshot_date.desc())
        .limit(1)
    )
    var_snap = var_result.scalar_one_or_none()

    # Concentration
    conc_result = await session.execute(
        select(ConcentrationAnalysis)
        .where(ConcentrationAnalysis.portfolio_id == portfolio_id)
        .order_by(ConcentrationAnalysis.snapshot_date.desc())
        .limit(1)
    )
    conc_snap = conc_result.scalar_one_or_none()

    # Factor
    factor_result = await session.execute(
        select(FactorExposureSnapshot)
        .where(FactorExposureSnapshot.portfolio_id == portfolio_id)
        .order_by(FactorExposureSnapshot.snapshot_date.desc())
        .limit(1)
    )
    factor_snap = factor_result.scalar_one_or_none()

    snap_date = None
    var_summary = None
    conc_summary = None
    factor_summary = None

    if var_snap:
        snap_date = var_snap.snapshot_date
        var_summary = VaRResponse(
            portfolio_id=portfolio_id,
            snapshot_date=var_snap.snapshot_date,
            var_1d_95=_opt_float(var_snap.var_1d_95),
            var_1d_99=_opt_float(var_snap.var_1d_99),
            var_10d_95=_opt_float(var_snap.var_10d_95),
            var_10d_99=_opt_float(var_snap.var_10d_99),
            undiversified_var=_opt_float(var_snap.undiversified_var),
            diversification_ratio=_opt_float(var_snap.diversification_ratio),
            portfolio_nav=_opt_float(var_snap.portfolio_nav),
            method=var_snap.method,
        )

    if conc_snap:
        snap_date = snap_date or conc_snap.snapshot_date
        conc_summary = _build_concentration_response(portfolio_id, conc_snap)

    if factor_snap:
        snap_date = snap_date or factor_snap.snapshot_date
        factor_summary = _build_factor_response(portfolio_id, factor_snap)

    return RiskDashboardResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap_date,
        var_summary=var_summary,
        concentration_summary=conc_summary,
        factor_summary=factor_summary,
    )


# ══════════════════════════════════════════════════════════════════════
# VaR endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/risk/var",
    response_model=VaRResponse | None,
)
async def get_var_summary(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get latest VaR snapshot for a portfolio."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PortfolioVarSnapshot)
        .where(PortfolioVarSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioVarSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    return VaRResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap.snapshot_date,
        var_1d_95=_opt_float(snap.var_1d_95),
        var_1d_99=_opt_float(snap.var_1d_99),
        var_10d_95=_opt_float(snap.var_10d_95),
        var_10d_99=_opt_float(snap.var_10d_99),
        undiversified_var=_opt_float(snap.undiversified_var),
        diversification_ratio=_opt_float(snap.diversification_ratio),
        portfolio_nav=_opt_float(snap.portfolio_nav),
        method=snap.method,
    )


@router.get(
    "/portfolios/{portfolio_id}/risk/var/decomposition",
    response_model=VaRDecompositionResponse | None,
)
async def get_var_decomposition(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get VaR decomposition: component, marginal, incremental."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PortfolioVarSnapshot)
        .where(PortfolioVarSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioVarSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    return VaRDecompositionResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap.snapshot_date,
        marginal_var=snap.marginal_var,
        component_var=snap.component_var,
        incremental_var=snap.incremental_var,
    )


# ══════════════════════════════════════════════════════════════════════
# Concentration endpoints
# ══════════════════════════════════════════════════════════════════════


def _build_concentration_response(
    portfolio_id: uuid.UUID, snap: ConcentrationAnalysis
) -> ConcentrationResponse:
    sector_entries = _parse_sector_concentration(snap.sector_detail)
    geo_detail = snap.geographic_detail if isinstance(snap.geographic_detail, list) else (
        snap.geographic_detail.get("regions", []) if snap.geographic_detail else []
    )
    return ConcentrationResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap.snapshot_date,
        hhi_position=_opt_float(snap.hhi_position),
        hhi_sector=_opt_float(snap.hhi_sector),
        hhi_industry=_opt_float(snap.hhi_industry),
        largest_position_weight=_opt_float(snap.largest_position_weight),
        top_5_weight=_opt_float(snap.top_5_weight),
        top_10_weight=_opt_float(snap.top_10_weight),
        effective_num_positions=_opt_float(snap.effective_num_positions),
        concentration_classification=snap.concentration_classification,
        sector_detail=sector_entries,
        geographic_detail=geo_detail,
        flags=snap.flags,
    )


def _parse_sector_concentration(data: dict | list | None) -> list[SectorConcentrationEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("sectors", [])
    return [
        SectorConcentrationEntry(
            sector=item.get("sector", "Unknown"),
            weight=item.get("weight", 0.0),
            benchmark_weight=item.get("benchmark_weight"),
            active_weight=item.get("active_weight"),
        )
        for item in items
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/concentration",
    response_model=ConcentrationResponse | None,
)
async def get_concentration(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get all concentration metrics."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ConcentrationAnalysis)
        .where(ConcentrationAnalysis.portfolio_id == portfolio_id)
        .order_by(ConcentrationAnalysis.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    return _build_concentration_response(portfolio_id, snap)


@router.get(
    "/portfolios/{portfolio_id}/risk/concentration/sectors",
    response_model=list[SectorConcentrationEntry],
)
async def get_concentration_sectors(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get sector concentration breakdown."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ConcentrationAnalysis)
        .where(ConcentrationAnalysis.portfolio_id == portfolio_id)
        .order_by(ConcentrationAnalysis.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return []
    return _parse_sector_concentration(snap.sector_detail)


@router.get(
    "/portfolios/{portfolio_id}/risk/concentration/geographic",
    response_model=list[dict] | None,
)
async def get_concentration_geographic(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get geographic concentration breakdown.

    Returns None when no concentration snapshot has been computed yet (data
    source missing), matching the ``| None`` convention used by
    ``get_concentration``/``get_var_decomposition`` — distinct from a `[]`
    result, which means a snapshot exists but genuinely has no geographic
    exposure recorded.
    """
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ConcentrationAnalysis)
        .where(ConcentrationAnalysis.portfolio_id == portfolio_id)
        .order_by(ConcentrationAnalysis.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    if not snap.geographic_detail:
        return []
    if isinstance(snap.geographic_detail, list):
        return snap.geographic_detail
    return snap.geographic_detail.get("regions", [])


# ══════════════════════════════════════════════════════════════════════
# Factor Exposure endpoints
# ══════════════════════════════════════════════════════════════════════


def _build_factor_response(
    portfolio_id: uuid.UUID, snap: FactorExposureSnapshot
) -> FactorExposureResponse:
    return FactorExposureResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap.snapshot_date,
        value_exposure=_opt_float(snap.value_exposure),
        growth_exposure=_opt_float(snap.growth_exposure),
        momentum_exposure=_opt_float(snap.momentum_exposure),
        quality_exposure=_opt_float(snap.quality_exposure),
        size_exposure=_opt_float(snap.size_exposure),
        low_vol_exposure=_opt_float(snap.low_vol_exposure),
        benchmark_value=_opt_float(snap.benchmark_value),
        benchmark_growth=_opt_float(snap.benchmark_growth),
        benchmark_momentum=_opt_float(snap.benchmark_momentum),
        benchmark_quality=_opt_float(snap.benchmark_quality),
        benchmark_size=_opt_float(snap.benchmark_size),
        benchmark_low_vol=_opt_float(snap.benchmark_low_vol),
        active_exposures=snap.active_exposures,
        factor_contributions=snap.factor_contributions,
        unintended_flags=snap.unintended_flags,
    )


@router.get(
    "/portfolios/{portfolio_id}/risk/factors",
    response_model=FactorExposureResponse | None,
)
async def get_factor_exposure(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get latest factor exposure summary."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(FactorExposureSnapshot)
        .where(FactorExposureSnapshot.portfolio_id == portfolio_id)
        .order_by(FactorExposureSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    return _build_factor_response(portfolio_id, snap)


@router.get(
    "/portfolios/{portfolio_id}/risk/factors/history",
    response_model=list[FactorHistoryEntry],
)
async def get_factor_history(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get factor exposure over time."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(FactorExposureSnapshot)
        .where(FactorExposureSnapshot.portfolio_id == portfolio_id)
        .order_by(FactorExposureSnapshot.snapshot_date.asc())
    )
    rows = result.scalars().all()
    return [
        FactorHistoryEntry(
            snapshot_date=snap.snapshot_date,
            value_exposure=_opt_float(snap.value_exposure),
            growth_exposure=_opt_float(snap.growth_exposure),
            momentum_exposure=_opt_float(snap.momentum_exposure),
            quality_exposure=_opt_float(snap.quality_exposure),
            size_exposure=_opt_float(snap.size_exposure),
            low_vol_exposure=_opt_float(snap.low_vol_exposure),
        )
        for snap in rows
    ]


@router.get(
    "/portfolios/{portfolio_id}/risk/factors/unintended",
    response_model=dict | None,
)
async def get_unintended_factors(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get unintended factor exposure flags."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(FactorExposureSnapshot)
        .where(FactorExposureSnapshot.portfolio_id == portfolio_id)
        .order_by(FactorExposureSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    return snap.unintended_flags


# ══════════════════════════════════════════════════════════════════════
# Stress Testing endpoints
# ══════════════════════════════════════════════════════════════════════


async def _load_position_dicts(
    session: AsyncSession, portfolio_id: uuid.UUID
) -> list[dict]:
    """Load open positions for engine consumption.

    Resolves each position's real asset class, equity beta (Blume-adjusted
    OLS regression vs the market benchmark, reusing e2_wacc's beta engine),
    and bond duration (from coupon/maturity via treasury_analytics) —
    previously every position was hardcoded to equity/beta=1.0/duration=0.0
    regardless of what it actually held, so stress tests always applied a
    uniform equity shock and never modeled rate/spread risk on bonds.
    """
    result = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    positions = list(result.scalars().all())

    dicts = []
    for pos in positions:
        asset_class = "equity"
        beta = 1.0
        duration = 0.0
        spread_duration = 0.0

        sec = None
        if pos.security_id is not None:
            sec = (
                await session.execute(
                    select(Security).where(Security.security_id == pos.security_id)
                )
            ).scalar_one_or_none()

        if sec is not None and sec.asset_class == "FIXED_INCOME":
            asset_class = "bond"
            fi = (
                await session.execute(
                    select(FixedIncomeDetails).where(
                        FixedIncomeDetails.security_id == pos.security_id
                    )
                )
            ).scalar_one_or_none()
            if (
                fi is not None
                and fi.coupon_rate is not None
                and sec.maturity_date is not None
                and pos.closing_price
            ):
                years = (sec.maturity_date - date.today()).days / 365.25
                if years > 0:
                    face = float(fi.face_value or 100.0)
                    price = float(pos.closing_price)
                    ytm = treasury_analytics.compute_treasury_ytm(
                        float(fi.coupon_rate), face, price, years
                    )
                    dur = treasury_analytics.compute_duration_convexity(
                        ytm, float(fi.coupon_rate), years
                    )
                    duration = dur["modified_duration"]
                    # Approximation: for a fixed-rate bond, spread duration
                    # is close to modified (interest-rate) duration.
                    spread_duration = dur["modified_duration"]
        elif sec is not None:
            adjusted_beta, _r2, _n = await e2_wacc._compute_beta(session, pos.security_id)
            if adjusted_beta is not None:
                beta = adjusted_beta

        dicts.append({
            "ticker": pos.ticker,
            "market_value": float(pos.market_value) if pos.market_value is not None else 0.0,
            "asset_class": asset_class,
            "beta": beta,
            "duration": duration,
            "spread_duration": spread_duration,
        })
    return dicts


async def load_position_dicts_with_classification(
    session: AsyncSession, portfolio_id: uuid.UUID
) -> list[dict]:
    """Load open positions with sector/industry/country/beta for the
    concentration/factor/drift/compliance engines.

    Shared by ``set_target_allocation`` (below) and
    ``scripts/run_portfolio_risk_batch.py`` so both the on-demand drift
    endpoint and the scheduled snapshot job build positions the same way
    instead of two independently-drifting implementations.

    sector/industry come from ``Entity.gics_sector``/``gics_industry`` (the
    2-digit/6-digit GICS codes already used as-is elsewhere in this
    codebase, e.g. e4_screening's categorical filters -- there is no
    separate human-readable name table). beta reads the already-scheduled
    E7/E1 ``beta_market`` AnalyticsResult metric (populated daily by the
    ``analytics_quant_weekly``/``analytics_ratios`` batch jobs) rather than
    recomputing an OLS regression per position on every call.
    """
    result = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    positions = list(result.scalars().all())

    dicts: list[dict] = []
    for pos in positions:
        sector = "Unknown"
        industry = "Unknown"
        country = "Unknown"
        beta = 1.0

        if pos.security_id is not None:
            sec = (
                await session.execute(
                    select(Security).where(Security.security_id == pos.security_id)
                )
            ).scalar_one_or_none()
            if sec is not None and sec.issuer_entity_id is not None:
                entity = (
                    await session.execute(
                        select(Entity).where(Entity.entity_id == sec.issuer_entity_id)
                    )
                ).scalar_one_or_none()
                if entity is not None:
                    sector = entity.gics_sector or "Unknown"
                    industry = entity.gics_industry or "Unknown"
                    country = entity.domicile_country or entity.incorporation_country or "Unknown"

            beta_row = (
                await session.execute(
                    select(AnalyticsResult.value)
                    .where(
                        AnalyticsResult.security_id == pos.security_id,
                        AnalyticsResult.metric_name == "beta_market",
                    )
                    .order_by(AnalyticsResult.as_of_date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if beta_row is not None:
                beta = float(beta_row)

        dicts.append({
            "ticker": pos.ticker,
            "security_id": pos.security_id,
            "market_value": float(pos.market_value) if pos.market_value is not None else 0.0,
            "sector": sector,
            "industry": industry,
            "country": country,
            "beta": beta,
        })
    return dicts


@router.post(
    "/portfolios/{portfolio_id}/risk/stress/historical",
    response_model=StressTestResponse,
    status_code=201,
)
async def run_historical_stress_test(
    portfolio_id: uuid.UUID,
    body: StressTestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a historical stress test scenario via the portfolio risk engine."""
    portfolio = await _get_portfolio(session, portfolio_id)

    today = date.today()
    positions = await _load_position_dicts(session, portfolio_id)
    portfolio_nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)

    if not positions:
        # No positions to stress — return a zero-result snapshot rather than
        # fabricating numbers.
        engine_result = portfolio_risk_engine.StressTestResult(
            scenario_name=body.scenario_name,
            scenario_type="historical",
            total_pnl_dollar=0.0,
            total_pnl_percent=0.0,
            max_drawdown_pct=0.0,
            recovery_time_months=0.0,
            per_position_pnl={},
            worst_positions=[],
        )
    else:
        try:
            engine_result = portfolio_risk_engine.run_stress_test(
                positions=positions,
                scenario_name=body.scenario_name,
                portfolio_nav=portfolio_nav,
                custom_params=body.shocks,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    result_record = PortfolioStressTestResult(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        snapshot_date=today,
        scenario_name=engine_result.scenario_name,
        scenario_type="HISTORICAL",
        total_pnl_dollar=Decimal(str(engine_result.total_pnl_dollar)),
        total_pnl_percent=Decimal(str(engine_result.total_pnl_percent)),
        max_drawdown_pct=Decimal(str(engine_result.max_drawdown_pct)),
        recovery_time_months=Decimal(str(engine_result.recovery_time_months)),
        per_position_pnl=engine_result.per_position_pnl,
        worst_positions={"worst": engine_result.worst_positions},
        scenario_params=body.shocks,
    )
    session.add(result_record)
    await session.commit()
    await session.refresh(result_record)

    return StressTestResponse(
        portfolio_id=portfolio_id,
        snapshot_date=today,
        scenario_name=engine_result.scenario_name,
        scenario_type="HISTORICAL",
        total_pnl_dollar=float(result_record.total_pnl_dollar),
        total_pnl_percent=float(result_record.total_pnl_percent),
        max_drawdown_pct=float(result_record.max_drawdown_pct),
        recovery_time_months=float(result_record.recovery_time_months),
        per_position_pnl=result_record.per_position_pnl,
        worst_positions=result_record.worst_positions,
        scenario_params=result_record.scenario_params,
    )


@router.post(
    "/portfolios/{portfolio_id}/risk/stress/hypothetical",
    response_model=StressTestResponse,
    status_code=201,
)
async def run_hypothetical_stress_test(
    portfolio_id: uuid.UUID,
    body: StressTestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a hypothetical (custom shock) stress test via the portfolio risk engine."""
    portfolio = await _get_portfolio(session, portfolio_id)

    today = date.today()
    positions = await _load_position_dicts(session, portfolio_id)
    portfolio_nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)

    shocks = body.shocks or {}
    equity_shock = float(shocks.get("equity_shock", -0.10))
    rate_shock_bps = float(shocks.get("rate_shock_bps", 0.0))
    spread_shock_bps = float(shocks.get("spread_shock_bps", 0.0))

    if not positions:
        engine_result = portfolio_risk_engine.StressTestResult(
            scenario_name=body.scenario_name,
            scenario_type="hypothetical",
            total_pnl_dollar=0.0,
            total_pnl_percent=0.0,
            max_drawdown_pct=0.0,
            recovery_time_months=0.0,
            per_position_pnl={},
            worst_positions=[],
        )
    else:
        engine_result = portfolio_risk_engine.run_hypothetical_stress(
            positions=positions,
            equity_shock=equity_shock,
            rate_shock_bps=rate_shock_bps,
            spread_shock_bps=spread_shock_bps,
            portfolio_nav=portfolio_nav,
        )

    result_record = PortfolioStressTestResult(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        snapshot_date=today,
        scenario_name=body.scenario_name,
        scenario_type="HYPOTHETICAL",
        total_pnl_dollar=Decimal(str(engine_result.total_pnl_dollar)),
        total_pnl_percent=Decimal(str(engine_result.total_pnl_percent)),
        max_drawdown_pct=Decimal(str(engine_result.max_drawdown_pct)),
        recovery_time_months=Decimal(str(engine_result.recovery_time_months)),
        per_position_pnl=engine_result.per_position_pnl,
        worst_positions={"worst": engine_result.worst_positions},
        scenario_params=shocks,
    )
    session.add(result_record)
    await session.commit()
    await session.refresh(result_record)

    return StressTestResponse(
        portfolio_id=portfolio_id,
        snapshot_date=today,
        scenario_name=body.scenario_name,
        scenario_type="HYPOTHETICAL",
        total_pnl_dollar=float(result_record.total_pnl_dollar),
        total_pnl_percent=float(result_record.total_pnl_percent),
        max_drawdown_pct=float(result_record.max_drawdown_pct),
        recovery_time_months=float(result_record.recovery_time_months),
        per_position_pnl=result_record.per_position_pnl,
        worst_positions=result_record.worst_positions,
        scenario_params=result_record.scenario_params,
    )


# Named scenarios offered by the pre-existing What-If Analysis panel
# (frontend/src/pages/portfolio/PortfolioDetail.tsx) -- mapped onto the
# same real equity/rate shock parameters AVAILABLE_SCENARIOS already uses
# for hypothetical stress tests, so "what if" reuses real, tested position
# math instead of a second implementation.
_WHATIF_SCENARIO_SHOCKS: dict[str, dict[str, float]] = {
    "market_drop_10": {"equity_shock": -0.10, "rate_shock_bps": 0.0, "spread_shock_bps": 0.0},
    "rate_hike_100bp": {"equity_shock": 0.0, "rate_shock_bps": 100.0, "spread_shock_bps": 0.0},
    # "sector_rotation" is deliberately unmapped: this codebase has no
    # per-sector-differentiated shock model anywhere (run_hypothetical_
    # stress only applies a single uniform equity/rate/spread shock across
    # all positions via beta/duration) -- projecting a sector-rotation
    # number would mean fabricating one, so it falls through to the
    # honest-null response below instead.
}


@router.post(
    "/portfolios/{portfolio_id}/what-if",
    response_model=WhatIfResponse,
    response_model_by_alias=True,
)
async def run_what_if(
    portfolio_id: uuid.UUID,
    body: WhatIfRequest,
    session: AsyncSession = Depends(get_session),
):
    """Named-scenario what-if projection for the portfolio's current
    holdings.

    [Gap fix] No route existed for this at all (DEEP_AUDIT_2026-07-16) --
    the frontend's What-If Analysis panel already POSTs
    ``{scenario}`` and reads back ``{projectedNavChange, projectedPnl}``
    (see the "always errors today" comment in PortfolioDetail.tsx), so
    this always failed. Computed via the same real
    portfolio_risk_engine.run_hypothetical_stress used by
    ``/risk/stress/hypothetical``, applied to live positions -- not
    whatif_engine.py's trade-level ``run_whatif_analysis`` (that engine
    expects an explicit list of proposed trades, which this scenario-name
    panel doesn't send; wiring it is a separate, larger gap than "the
    route doesn't exist").
    """
    portfolio = await _get_portfolio(session, portfolio_id)
    positions = await _load_position_dicts(session, portfolio_id)
    portfolio_nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)

    shock = _WHATIF_SCENARIO_SHOCKS.get(body.scenario)
    if not positions or portfolio_nav <= 0 or shock is None:
        return WhatIfResponse()

    result = portfolio_risk_engine.run_hypothetical_stress(
        positions=positions,
        equity_shock=shock["equity_shock"],
        rate_shock_bps=shock["rate_shock_bps"],
        spread_shock_bps=shock["spread_shock_bps"],
        portfolio_nav=portfolio_nav,
    )
    return WhatIfResponse(
        projected_nav_change=result.total_pnl_percent,
        projected_pnl=result.total_pnl_dollar,
    )


@router.get(
    "/portfolios/{portfolio_id}/risk/stress/results",
    response_model=list[StressTestResponse],
)
async def get_stress_test_results(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get past stress test results."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(PortfolioStressTestResult)
        .where(PortfolioStressTestResult.portfolio_id == portfolio_id)
        .order_by(PortfolioStressTestResult.snapshot_date.desc())
    )
    rows = result.scalars().all()
    return [
        StressTestResponse(
            portfolio_id=portfolio_id,
            snapshot_date=r.snapshot_date,
            scenario_name=r.scenario_name,
            scenario_type=r.scenario_type,
            total_pnl_dollar=_opt_float(r.total_pnl_dollar),
            total_pnl_percent=_opt_float(r.total_pnl_percent),
            max_drawdown_pct=_opt_float(r.max_drawdown_pct),
            recovery_time_months=_opt_float(r.recovery_time_months),
            per_position_pnl=r.per_position_pnl,
            worst_positions=r.worst_positions,
            scenario_params=r.scenario_params,
        )
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Compliance endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/{portfolio_id}/compliance",
    response_model=ComplianceSummaryResponse,
)
async def get_compliance_summary(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get compliance summary for a portfolio."""
    await _get_portfolio(session, portfolio_id)

    rules_result = await session.execute(
        select(ComplianceRule)
        .where(ComplianceRule.portfolio_id == portfolio_id)
        .order_by(ComplianceRule.rule_name)
    )
    rules = rules_result.scalars().all()

    results_result = await session.execute(
        select(ComplianceResult)
        .where(ComplianceResult.portfolio_id == portfolio_id)
        .order_by(ComplianceResult.check_date.desc())
    )
    results = results_result.scalars().all()

    passing = sum(1 for r in results if r.status == "PASS")
    warning = sum(1 for r in results if r.status == "WARNING")
    breaching = sum(1 for r in results if r.status == "BREACH")

    rule_responses = [
        ComplianceRuleResponse(
            rule_id=rule.rule_id,
            portfolio_id=rule.portfolio_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            rule_definition=rule.rule_definition,
            threshold=_opt_float(rule.threshold),
            upper_threshold=_opt_float(rule.upper_threshold),
            comparison=rule.comparison,
            severity=rule.severity,
            is_active=rule.is_active,
        )
        for rule in rules
    ]

    result_responses = [
        ComplianceResultResponse(
            result_id=r.result_id,
            portfolio_id=r.portfolio_id,
            rule_id=r.rule_id,
            check_date=r.check_date,
            status=r.status,
            current_value=_opt_float(r.current_value),
            threshold_value=_opt_float(r.threshold_value),
            breach_positions=r.breach_positions,
            notes=r.notes,
        )
        for r in results
    ]

    return ComplianceSummaryResponse(
        portfolio_id=portfolio_id,
        total_rules=len(rules),
        passing=passing,
        warning=warning,
        breaching=breaching,
        rules=rule_responses,
        latest_results=result_responses,
    )


@router.get(
    "/portfolios/{portfolio_id}/compliance/rules",
    response_model=list[ComplianceRuleResponse],
)
async def list_compliance_rules(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """List compliance rules for a portfolio."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ComplianceRule)
        .where(ComplianceRule.portfolio_id == portfolio_id)
        .order_by(ComplianceRule.rule_name)
    )
    rules = result.scalars().all()
    return [
        ComplianceRuleResponse(
            rule_id=rule.rule_id,
            portfolio_id=rule.portfolio_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            rule_definition=rule.rule_definition,
            threshold=_opt_float(rule.threshold),
            upper_threshold=_opt_float(rule.upper_threshold),
            comparison=rule.comparison,
            severity=rule.severity,
            is_active=rule.is_active,
        )
        for rule in rules
    ]


@router.post(
    "/portfolios/{portfolio_id}/compliance/rules",
    response_model=ComplianceRuleResponse,
    status_code=201,
)
async def create_compliance_rule(
    portfolio_id: uuid.UUID,
    body: ComplianceRuleCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new compliance rule."""
    await _get_portfolio(session, portfolio_id)

    rule = ComplianceRule(
        rule_id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        rule_name=body.rule_name,
        rule_type=body.rule_type,
        rule_definition=body.rule_definition,
        threshold=Decimal(str(body.threshold)) if body.threshold is not None else None,
        upper_threshold=Decimal(str(body.upper_threshold)) if body.upper_threshold is not None else None,
        comparison=body.comparison,
        severity=body.severity,
        is_active=body.is_active,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return ComplianceRuleResponse(
        rule_id=rule.rule_id,
        portfolio_id=rule.portfolio_id,
        rule_name=rule.rule_name,
        rule_type=rule.rule_type,
        rule_definition=rule.rule_definition,
        threshold=_opt_float(rule.threshold),
        upper_threshold=_opt_float(rule.upper_threshold),
        comparison=rule.comparison,
        severity=rule.severity,
        is_active=rule.is_active,
    )


@router.put(
    "/portfolios/{portfolio_id}/compliance/rules/{rule_id}",
    response_model=ComplianceRuleResponse,
)
async def update_compliance_rule(
    portfolio_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: ComplianceRuleUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing compliance rule."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ComplianceRule).where(
            ComplianceRule.rule_id == rule_id,
            ComplianceRule.portfolio_id == portfolio_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Compliance rule not found")

    if body.rule_name is not None:
        rule.rule_name = body.rule_name
    if body.rule_type is not None:
        rule.rule_type = body.rule_type
    if body.rule_definition is not None:
        rule.rule_definition = body.rule_definition
    if body.threshold is not None:
        rule.threshold = Decimal(str(body.threshold))
    if body.upper_threshold is not None:
        rule.upper_threshold = Decimal(str(body.upper_threshold))
    if body.comparison is not None:
        rule.comparison = body.comparison
    if body.severity is not None:
        rule.severity = body.severity
    if body.is_active is not None:
        rule.is_active = body.is_active

    await session.commit()
    await session.refresh(rule)

    return ComplianceRuleResponse(
        rule_id=rule.rule_id,
        portfolio_id=rule.portfolio_id,
        rule_name=rule.rule_name,
        rule_type=rule.rule_type,
        rule_definition=rule.rule_definition,
        threshold=_opt_float(rule.threshold),
        upper_threshold=_opt_float(rule.upper_threshold),
        comparison=rule.comparison,
        severity=rule.severity,
        is_active=rule.is_active,
    )


@router.delete(
    "/portfolios/{portfolio_id}/compliance/rules/{rule_id}",
    status_code=204,
)
async def delete_compliance_rule(
    portfolio_id: uuid.UUID,
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Delete a compliance rule."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ComplianceRule).where(
            ComplianceRule.rule_id == rule_id,
            ComplianceRule.portfolio_id == portfolio_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Compliance rule not found")

    await session.delete(rule)
    await session.commit()
    return None


@router.get(
    "/portfolios/{portfolio_id}/compliance/results",
    response_model=list[ComplianceResultResponse],
)
async def get_compliance_results(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get compliance check results history."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(ComplianceResult)
        .where(ComplianceResult.portfolio_id == portfolio_id)
        .order_by(ComplianceResult.check_date.desc())
    )
    rows = result.scalars().all()
    return [
        ComplianceResultResponse(
            result_id=r.result_id,
            portfolio_id=r.portfolio_id,
            rule_id=r.rule_id,
            check_date=r.check_date,
            status=r.status,
            current_value=_opt_float(r.current_value),
            threshold_value=_opt_float(r.threshold_value),
            breach_positions=r.breach_positions,
            notes=r.notes,
        )
        for r in rows
    ]


@router.post(
    "/portfolios/{portfolio_id}/compliance/pre-trade-check",
    response_model=PreTradeCheckResponse,
)
async def pre_trade_check(
    portfolio_id: uuid.UUID,
    body: PreTradeCheckRequest,
    session: AsyncSession = Depends(get_session),
):
    """Validate a proposed trade against compliance rules."""
    await _get_portfolio(session, portfolio_id)

    # Fetch active rules
    result = await session.execute(
        select(ComplianceRule)
        .where(
            ComplianceRule.portfolio_id == portfolio_id,
            ComplianceRule.is_active.is_(True),
        )
    )
    rules = result.scalars().all()

    violations: list[dict] = []
    warnings: list[dict] = []

    trade_value = body.shares * body.price

    # Load NAV inputs for ratio-based checks (sector/single-security/leverage).
    portfolio_obj = await _get_portfolio(session, portfolio_id)
    pos_rows = await session.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.status == "OPEN",
        )
    )
    positions = list(pos_rows.scalars().all())
    total_mv = sum(float(p.market_value) for p in positions if p.market_value is not None)
    nav = float(portfolio_obj.current_cash or 0.0) + total_mv
    proposed_nav = nav if nav > 0 else (trade_value if trade_value > 0 else 1.0)

    def _record(rule, message: str, *, severity: str | None = None) -> None:
        # Any matching rule blocks the trade (goes into violations).
        # ``warnings`` is reserved for soft signals like "approaching
        # limit" that we don't currently emit.
        violations.append({
            "rule_id": str(rule.rule_id),
            "rule_name": rule.rule_name,
            "rule_type": rule.rule_type,
            "severity": severity or rule.severity,
            "message": message,
        })

    for rule in rules:
        if rule.threshold is None:
            continue
        threshold = float(rule.threshold)
        rule_type = (rule.rule_type or "").upper()

        if rule_type == "POSITION_LIMIT":
            if trade_value > threshold:
                _record(rule, f"Trade value {trade_value:.2f} exceeds limit {threshold:.2f}")

        elif rule_type == "SINGLE_SECURITY_LIMIT":
            existing_mv = sum(
                float(p.market_value) for p in positions
                if p.ticker == body.ticker and p.market_value is not None
            )
            new_mv = existing_mv + (trade_value if body.action.upper() == "BUY" else -trade_value)
            ratio = new_mv / proposed_nav if proposed_nav > 0 else 0.0
            if ratio > threshold:
                _record(
                    rule,
                    f"{body.ticker} would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)",
                )

        elif rule_type == "CONCENTRATION_LIMIT":
            # Largest single position weight (post-trade approximation).
            weights = [
                (p.ticker, float(p.market_value)) for p in positions
                if p.market_value is not None
            ]
            top = max((mv for _, mv in weights), default=0.0)
            if body.action.upper() == "BUY":
                top = max(top, trade_value)
            ratio = top / proposed_nav if proposed_nav > 0 else 0.0
            if ratio > threshold:
                _record(
                    rule,
                    f"Largest holding would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)",
                )

        elif rule_type == "SECTOR_LIMIT":
            sector_target = (rule.rule_definition or {}).get("sector") if isinstance(rule.rule_definition, dict) else None
            if sector_target:
                same_sector_mv = sum(
                    float(p.market_value) for p in positions
                    if p.market_value is not None
                    and (getattr(p, "sector", None) or "").lower() == sector_target.lower()
                )
                ratio = same_sector_mv / proposed_nav if proposed_nav > 0 else 0.0
                if ratio > threshold:
                    _record(
                        rule,
                        f"Sector {sector_target} would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)",
                    )

        elif rule_type == "LEVERAGE_LIMIT":
            cash_after = float(portfolio_obj.current_cash or 0.0)
            if body.action.upper() == "BUY":
                cash_after -= trade_value
            leverage = (proposed_nav - cash_after) / proposed_nav if proposed_nav > 0 else 0.0
            if leverage > threshold:
                _record(
                    rule,
                    f"Leverage would be {leverage*100:.1f}% (limit {threshold*100:.1f}%)",
                )

    approved = len(violations) == 0

    return PreTradeCheckResponse(
        portfolio_id=portfolio_id,
        ticker=body.ticker,
        action=body.action,
        approved=approved,
        violations=violations,
        warnings=warnings,
    )


# ══════════════════════════════════════════════════════════════════════
# Drift endpoints
# ══════════════════════════════════════════════════════════════════════


def _parse_position_drifts(data: dict | list | None) -> list[PositionDriftEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("positions", [])
    return [
        PositionDriftEntry(
            ticker=item.get("ticker", "N/A"),
            target_weight=item.get("target_weight", 0.0),
            current_weight=item.get("current_weight", 0.0),
            drift_pct=item.get("drift_pct", 0.0),
        )
        for item in items
    ]


def _parse_sector_drifts(data: dict | list | None) -> list[SectorDriftEntry]:
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("sectors", [])
    return [
        SectorDriftEntry(
            sector=item.get("sector", "Unknown"),
            target_weight=item.get("target_weight", 0.0),
            current_weight=item.get("current_weight", 0.0),
            drift_pct=item.get("drift_pct", 0.0),
        )
        for item in items
    ]


@router.get(
    "/portfolios/{portfolio_id}/drift",
    response_model=DriftResponse | None,
)
async def get_current_drift(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get current drift analysis."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(DriftSnapshot)
        .where(DriftSnapshot.portfolio_id == portfolio_id)
        .order_by(DriftSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None

    return DriftResponse(
        portfolio_id=portfolio_id,
        snapshot_date=snap.snapshot_date,
        total_drift_pct=_opt_float(snap.total_drift_pct),
        max_position_drift_pct=_opt_float(snap.max_position_drift_pct),
        max_sector_drift_pct=_opt_float(snap.max_sector_drift_pct),
        drift_classification=snap.drift_classification,
        rebalance_needed=snap.rebalance_needed,
        position_drifts=_parse_position_drifts(snap.position_drifts),
        sector_drifts=_parse_sector_drifts(snap.sector_drifts),
        target_allocation=snap.target_allocation,
    )


@router.get(
    "/portfolios/{portfolio_id}/drift/history",
    response_model=list[DriftResponse],
)
async def get_drift_history(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get drift analysis over time."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(DriftSnapshot)
        .where(DriftSnapshot.portfolio_id == portfolio_id)
        .order_by(DriftSnapshot.snapshot_date.asc())
    )
    rows = result.scalars().all()
    return [
        DriftResponse(
            portfolio_id=portfolio_id,
            snapshot_date=snap.snapshot_date,
            total_drift_pct=_opt_float(snap.total_drift_pct),
            max_position_drift_pct=_opt_float(snap.max_position_drift_pct),
            max_sector_drift_pct=_opt_float(snap.max_sector_drift_pct),
            drift_classification=snap.drift_classification,
            rebalance_needed=snap.rebalance_needed,
            position_drifts=_parse_position_drifts(snap.position_drifts),
            sector_drifts=_parse_sector_drifts(snap.sector_drifts),
            target_allocation=snap.target_allocation,
        )
        for snap in rows
    ]


@router.get(
    "/portfolios/{portfolio_id}/drift/rebalance",
    response_model=RebalanceSuggestionResponse,
)
async def get_rebalance_suggestions(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get rebalancing suggestions based on current drift."""
    await _get_portfolio(session, portfolio_id)

    result = await session.execute(
        select(DriftSnapshot)
        .where(DriftSnapshot.portfolio_id == portfolio_id)
        .order_by(DriftSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()

    if not snap:
        return RebalanceSuggestionResponse(
            portfolio_id=portfolio_id,
            rebalance_needed=False,
        )

    suggestions: list[dict] = []
    position_drifts = _parse_position_drifts(snap.position_drifts)
    for pd_entry in position_drifts:
        if pd_entry.drift_pct is not None and abs(pd_entry.drift_pct) > 0.02:  # > 2% drift threshold
            action = "SELL" if pd_entry.drift_pct > 0 else "BUY"
            suggestions.append({
                "ticker": pd_entry.ticker,
                "action": action,
                "current_weight": pd_entry.current_weight,
                "target_weight": pd_entry.target_weight,
                "drift_pct": pd_entry.drift_pct,
            })

    return RebalanceSuggestionResponse(
        portfolio_id=portfolio_id,
        rebalance_needed=snap.rebalance_needed or False,
        total_drift_pct=_opt_float(snap.total_drift_pct),
        suggestions=suggestions,
    )


def _empty_trade_list(portfolio_id: str, portfolio_name: str, reason: str) -> trade_list_engine.TradeList:
    return trade_list_engine.TradeList(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        orders=[],
        summary=trade_list_engine.TradeListSummary(
            total_orders=0, buy_count=0, sell_count=0, total_buy_notional=0.0,
            total_sell_notional=0.0, net_notional=0.0, estimated_commission=0.0,
            estimated_market_impact=0.0,
        ),
        metadata={"source": "drift_rebalance", "reason": reason},
    )


def _trade_list_to_response(tl: trade_list_engine.TradeList, portfolio_id: uuid.UUID) -> TradeListResponse:
    return TradeListResponse(
        portfolio_id=portfolio_id,
        portfolio_name=tl.portfolio_name,
        generated_at=tl.generated_at,
        orders=[TradeOrderEntry(**vars(o)) for o in tl.orders],
        summary=TradeListSummaryEntry(**vars(tl.summary)),
        metadata=tl.metadata,
    )


@router.get("/portfolios/{portfolio_id}/trade-list")
async def get_trade_list(
    portfolio_id: uuid.UUID,
    format: str = Query(default="json", description="json | csv | fix | ems"),
    order_type: str = Query(default="MARKET", description="MARKET | LIMIT | VWAP | TWAP"),
    time_in_force: str = Query(default="DAY", description="DAY | GTC | IOC"),
    session: AsyncSession = Depends(get_session),
):
    """Generate a broker-ready trade list from the portfolio's current
    drift vs. its stored target allocation.

    [Gap fix] trade_list_engine.py was a correct pure-computation module
    (rebalance-trades -> sized orders -> optimized sequence -> CSV/FIX/EMS
    export) with zero callers anywhere (DEEP_AUDIT_2026-07-16). Feeds
    drift_engine's real ``suggest_rebalance_trades`` output -- computed
    fresh from live positions and the stored target allocation, not
    ``/drift/rebalance``'s own duplicate 2%-threshold approximation -- into
    the trade-list engine, sized against today's closing prices.
    """
    portfolio = await _get_portfolio(session, portfolio_id)
    pid_str = str(portfolio_id)

    target_row = (
        await session.execute(
            select(DriftSnapshot)
            .where(DriftSnapshot.portfolio_id == portfolio_id)
            .order_by(DriftSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    target_allocation = target_row.target_allocation if target_row and target_row.target_allocation else None

    if not target_allocation:
        trade_list = _empty_trade_list(pid_str, portfolio.portfolio_name, "no target allocation set")
    else:
        positions = await load_position_dicts_with_classification(session, portfolio_id)
        nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)

        if nav <= 0 or not positions:
            trade_list = _empty_trade_list(pid_str, portfolio.portfolio_name, "no open positions")
        else:
            current_weights_pct = {p["ticker"]: p["market_value"] / nav * 100.0 for p in positions}
            target_weights_pct = {ticker: weight * 100.0 for ticker, weight in target_allocation.items()}
            position_drifts = drift_engine.compute_position_drift(current_weights_pct, target_weights_pct)
            rebalance_trades = drift_engine.suggest_rebalance_trades(position_drifts, nav)

            prices: dict[str, float] = {}
            for p in positions:
                if p["security_id"] is None:
                    continue
                row = (
                    await session.execute(
                        select(EODPrice.close)
                        .where(EODPrice.security_id == p["security_id"], EODPrice.close.isnot(None))
                        .order_by(EODPrice.price_date.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if row is not None:
                    prices[p["ticker"]] = float(row)

            trade_list = trade_list_engine.generate_trade_list(
                portfolio_id=pid_str,
                portfolio_name=portfolio.portfolio_name,
                rebalance_trades=rebalance_trades,
                positions=positions,
                prices=prices,
                portfolio_nav=nav,
                order_type=order_type,
                time_in_force=time_in_force,
            )

    if format == "json":
        return _trade_list_to_response(trade_list, portfolio_id)
    elif format == "csv":
        return PlainTextResponse(trade_list_engine.format_trade_list_csv(trade_list), media_type="text/csv")
    elif format == "fix":
        return trade_list_engine.format_trade_list_fix(trade_list)
    elif format == "ems":
        return trade_list_engine.format_trade_list_ems(trade_list)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.post(
    "/portfolios/{portfolio_id}/drift/target",
    response_model=DriftResponse,
    status_code=201,
)
async def set_target_allocation(
    portfolio_id: uuid.UUID,
    body: TargetAllocationRequest,
    session: AsyncSession = Depends(get_session),
):
    """Set a new target allocation and immediately compute real drift
    against it.

    [Bug fix] Previously hardcoded every drift metric to zero /
    classification "NONE" regardless of the portfolio's actual current
    weights -- only ``target_allocation`` itself was genuine, so every read
    of ``GET .../drift`` presented fabricated "no drift" numbers instead of
    an honest computation. Target weights arrive as decimal fractions
    (TargetAllocationRequest's documented 0.0-1.0 range) but
    ``drift_engine`` operates on percentage points (0-100, see its
    DRIFT_THRESHOLDS and ``suggest_rebalance_trades``'s ``/100.0`` NAV
    scaling) -- both weight dicts are scaled up before calling it.
    """
    portfolio = await _get_portfolio(session, portfolio_id)

    today = date.today()
    positions = await load_position_dicts_with_classification(session, portfolio_id)
    portfolio_nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)

    current_weights_pct = {
        p["ticker"]: (p["market_value"] / portfolio_nav * 100.0 if portfolio_nav > 0 else 0.0)
        for p in positions
    }
    target_weights_pct = {ticker: weight * 100.0 for ticker, weight in body.root.items()}
    positions_pct = [
        {**p, "weight": current_weights_pct.get(p["ticker"], 0.0)} for p in positions
    ]

    engine_result = drift_engine.analyze_drift(
        current_weights=current_weights_pct,
        target_weights=target_weights_pct,
        positions=positions_pct,
        target_sector_weights=None,  # not captured by TargetAllocationRequest -- honest gap
        portfolio_nav=portfolio_nav,
    )

    position_drifts = [
        {
            "ticker": d.ticker,
            "target_weight": d.target_weight,
            "current_weight": d.current_weight,
            "drift_pct": d.drift_pct,
        }
        for d in engine_result.position_drifts
    ]
    sector_drifts = [
        {
            "sector": d.sector,
            "target_weight": d.target_weight,
            "current_weight": d.current_weight,
            "drift_pct": d.drift_pct,
        }
        for d in engine_result.sector_drifts
    ]

    snap = DriftSnapshot(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        snapshot_date=today,
        total_drift_pct=Decimal(str(engine_result.total_drift_pct)),
        max_position_drift_pct=Decimal(str(engine_result.max_position_drift_pct)),
        max_sector_drift_pct=Decimal(str(engine_result.max_sector_drift_pct)),
        drift_classification=engine_result.classification,
        rebalance_needed=engine_result.rebalance_needed,
        position_drifts=position_drifts,
        sector_drifts=sector_drifts,
        target_allocation=body.root,
    )
    session.add(snap)
    await session.commit()
    await session.refresh(snap)

    return DriftResponse(
        portfolio_id=portfolio_id,
        snapshot_date=today,
        total_drift_pct=engine_result.total_drift_pct,
        max_position_drift_pct=engine_result.max_position_drift_pct,
        max_sector_drift_pct=engine_result.max_sector_drift_pct,
        drift_classification=engine_result.classification,
        rebalance_needed=engine_result.rebalance_needed,
        position_drifts=_parse_position_drifts(position_drifts),
        sector_drifts=_parse_sector_drifts(sector_drifts),
        target_allocation=body.root,
    )
