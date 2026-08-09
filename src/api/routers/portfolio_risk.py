"""Portfolio Risk Management API endpoints (Pillar 4 Phase 3)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import e2_wacc, portfolio_risk_engine, treasury_analytics
from src.services import portfolio_advisory
from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.security import FixedIncomeDetails, Security
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

    # Shared with the Layer-3 adviser's PreTradeComplianceTool
    # (src/ai/tools/portfolio.py) -- one rule-evaluation implementation,
    # not two that could drift apart. See
    # src/services/portfolio_advisory.py::check_pretrade_compliance.
    result = await portfolio_advisory.check_pretrade_compliance(
        session, portfolio_id, ticker=body.ticker, action=body.action,
        shares=body.shares, price=body.price,
    )

    return PreTradeCheckResponse(
        portfolio_id=portfolio_id,
        ticker=body.ticker,
        action=body.action,
        approved=result.approved,
        violations=result.violations,
        warnings=result.warnings,
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
    """Set or update target allocation for drift monitoring."""
    await _get_portfolio(session, portfolio_id)

    today = date.today()
    snap = DriftSnapshot(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        snapshot_date=today,
        total_drift_pct=Decimal("0.0000"),
        max_position_drift_pct=Decimal("0.0000"),
        max_sector_drift_pct=Decimal("0.0000"),
        drift_classification="NONE",
        rebalance_needed=False,
        target_allocation=body.root,
    )
    session.add(snap)
    await session.commit()
    await session.refresh(snap)

    return DriftResponse(
        portfolio_id=portfolio_id,
        snapshot_date=today,
        total_drift_pct=0.0,
        max_position_drift_pct=0.0,
        max_sector_drift_pct=0.0,
        drift_classification="NONE",
        rebalance_needed=False,
        position_drifts=[],
        sector_drifts=[],
        target_allocation=body.root,
    )
