"""Pillar 2: Risk Analytics API (Spec §7).

Endpoints for VaR, stress testing, factor exposures, fundamental risk,
volatility, beta, and drawdown analysis.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.config import settings
from src.engines.e2_wacc import _find_benchmark_security_id
from src.engines.e5_risk import RiskEngine, _load_returns, _mean, _std, _max_drawdown
from src.engines.e5_stress_scenarios import get_all_scenarios, get_scenario
from src.engines.e7_quant import QuantEngine
from src.models.analytics import AnalyticsResult
from src.models.risk import FactorExposure, StressTestResult, VaRResult
from src.models.security import Security, SecurityIdentifier
from src.schemas.risk import (
    BetaResponse,
    DrawdownResponse,
    FactorDetail,
    FactorExposureResponse,
    FundamentalRiskResponse,
    LeverageRiskResponse,
    LiquidityRiskResponse,
    PortfolioVaRRequest,
    StressScenarioSummary,
    StressTestRequest,
    StressTestResponse,
    StressTestScenarioResult,
    VaRResponse,
    VolatilityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics/risk", tags=["Risk Analytics"])

_engine = RiskEngine()
_quant_engine = QuantEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_security(session: AsyncSession, security_id: uuid.UUID) -> Security:
    result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    sec = result.scalar_one_or_none()
    if sec is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return sec


async def _get_metric_value(
    session: AsyncSession, security_id: uuid.UUID, metric_name: str
) -> float | None:
    result = await session.execute(
        select(AnalyticsResult.value)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.metric_name == metric_name,
        )
        .order_by(desc(AnalyticsResult.as_of_date))
        .limit(1)
    )
    val = result.scalar_one_or_none()
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# VaR
# ---------------------------------------------------------------------------

@router.get("/var/{security_id}", response_model=VaRResponse)
async def get_var(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Value at Risk summary for a single security."""
    sec = await _resolve_security(session, security_id)

    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return VaRResponse(
        security_id=security_id,
        calculation_date=date.today(),
        historical_var={
            "95_1d": out_map.get("var_historical_95_1d"),
            "99_1d": out_map.get("var_historical_99_1d"),
            "95_10d": out_map.get("var_historical_95_10d"),
            "99_10d": out_map.get("var_historical_99_10d"),
            "95_30d": out_map.get("var_historical_95_30d"),
            "99_30d": out_map.get("var_historical_99_30d"),
        },
        parametric_var={
            "95_1d": out_map.get("var_parametric_95_1d"),
            "99_1d": out_map.get("var_parametric_99_1d"),
        },
        expected_shortfall={
            "95_1d": out_map.get("cvar_95_1d"),
            "99_1d": out_map.get("cvar_99_1d"),
        },
        volatility={
            "annualized": out_map.get("annualized_volatility"),
            "daily": out_map.get("daily_volatility"),
            "skewness": out_map.get("skewness"),
            "kurtosis": out_map.get("kurtosis"),
        },
        max_drawdown=out_map.get("max_drawdown"),
    )


@router.post("/var/portfolio")
async def get_portfolio_var(
    body: PortfolioVaRRequest,
    session: AsyncSession = Depends(get_session),
):
    """Portfolio VaR (simplified: weighted sum of individual VaRs)."""
    total_var = 0.0
    results = []
    for pos in body.positions:
        sid = pos.get("security_id")
        weight = pos.get("weight", 1.0)
        if sid is None:
            continue
        try:
            sec_id = uuid.UUID(str(sid))
        except (ValueError, TypeError):
            continue
        outputs = await _engine.compute(session, sec_id)
        out_map = {o.metric_name: o.value for o in outputs}
        var_key = f"var_historical_{int(body.confidence * 100)}_{body.holding_period_days}d"
        var_val = out_map.get(var_key, 0.0) or 0.0
        weighted = var_val * weight
        total_var += weighted
        results.append({"security_id": str(sid), "weight": weight, "var": var_val})

    return {
        "portfolio_var": total_var,
        "confidence": body.confidence,
        "holding_period_days": body.holding_period_days,
        "positions": results,
    }


# ---------------------------------------------------------------------------
# Stress Testing
# ---------------------------------------------------------------------------

@router.get("/stress/scenarios", response_model=list[StressScenarioSummary])
async def list_stress_scenarios():
    """List all available stress scenarios."""
    scenarios = get_all_scenarios()
    return [
        StressScenarioSummary(
            name=name,
            label=s.get("label", name),
            scenario_type=s.get("type", "UNKNOWN"),
            description=s.get("description"),
        )
        for name, s in scenarios.items()
    ]


@router.post("/stress/run", response_model=StressTestResponse)
async def run_stress_test(
    body: StressTestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a stress test on a security."""
    await _resolve_security(session, body.security_id)
    result = await _engine.run_stress_test(
        session, body.security_id, body.scenario_name, body.shock_pct,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found or no data")

    return StressTestResponse(
        security_id=body.security_id,
        scenarios=[
            StressTestScenarioResult(
                scenario_name=result.scenario_name,
                scenario_type=result.scenario_type,
                pnl_percent=result.pnl_percent,
                max_drawdown=result.max_drawdown,
                worst_day=result.worst_day,
                best_day=result.best_day,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Factor Exposures
# ---------------------------------------------------------------------------

@router.get("/factors/{security_id}", response_model=FactorExposureResponse)
async def get_factor_exposures(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Style-factor exposures for a security."""
    sec = await _resolve_security(session, security_id)
    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    factor_names = [
        "factor_momentum", "factor_low_vol", "factor_value",
        "factor_size", "factor_quality", "factor_growth", "factor_dividend",
    ]
    factors: dict[str, FactorDetail] = {}
    for fn in factor_names:
        if fn in out_map:
            short = fn.replace("factor_", "").upper()
            factors[short] = FactorDetail(raw_value=out_map[fn])

    return FactorExposureResponse(
        security_id=security_id,
        calculation_date=date.today(),
        factors=factors,
    )


# ---------------------------------------------------------------------------
# Fundamental Risk
# ---------------------------------------------------------------------------

@router.get("/fundamental/{security_id}", response_model=FundamentalRiskResponse)
async def get_fundamental_risk(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Fundamental risk dashboard."""
    sec = await _resolve_security(session, security_id)
    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return FundamentalRiskResponse(
        security_id=security_id,
        leverage_risk={
            "net_debt_to_ebitda": out_map.get("risk_net_debt_to_ebitda"),
            "interest_coverage": out_map.get("risk_interest_coverage"),
            "debt_to_equity": out_map.get("risk_debt_to_equity"),
            "current_ratio": out_map.get("risk_current_ratio"),
        },
        earnings_risk={},
        liquidity_risk={
            "avg_volume_20d": out_map.get("avg_volume_20d"),
            "avg_volume_60d": out_map.get("avg_volume_60d"),
        },
        leverage_score=out_map.get("risk_leverage_score"),
    )


@router.get("/fundamental/{security_id}/leverage", response_model=LeverageRiskResponse)
async def get_leverage_risk(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Detailed leverage risk."""
    sec = await _resolve_security(session, security_id)
    nde = await _get_metric_value(session, security_id, "net_debt_to_ebitda")
    ic = await _get_metric_value(session, security_id, "interest_coverage")
    dte = await _get_metric_value(session, security_id, "debt_to_equity")
    cr = await _get_metric_value(session, security_id, "current_ratio")

    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return LeverageRiskResponse(
        security_id=security_id,
        net_debt_to_ebitda=nde,
        interest_coverage=ic,
        debt_to_equity=dte,
        current_ratio=cr,
        leverage_score=out_map.get("risk_leverage_score"),
    )


@router.get("/fundamental/{security_id}/liquidity", response_model=LiquidityRiskResponse)
async def get_liquidity_risk(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Detailed liquidity risk."""
    sec = await _resolve_security(session, security_id)
    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return LiquidityRiskResponse(
        security_id=security_id,
        avg_volume_20d=out_map.get("avg_volume_20d"),
        avg_volume_60d=out_map.get("avg_volume_60d"),
        bid_ask_proxy=out_map.get("bid_ask_proxy"),
        amihud_illiquidity=out_map.get("amihud_illiquidity"),
    )


# ---------------------------------------------------------------------------
# Volatility & Beta
# ---------------------------------------------------------------------------

@router.get("/volatility/{security_id}", response_model=VolatilityResponse)
async def get_volatility(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Historical volatility metrics."""
    sec = await _resolve_security(session, security_id)
    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return VolatilityResponse(
        security_id=security_id,
        annualized_volatility=out_map.get("annualized_volatility"),
        daily_volatility=out_map.get("daily_volatility"),
        skewness=out_map.get("skewness"),
        kurtosis=out_map.get("kurtosis"),
        max_drawdown=out_map.get("max_drawdown"),
    )


async def _resolve_benchmark_security_id(session: AsyncSession, ticker: str) -> uuid.UUID | None:
    """Resolve an arbitrary benchmark ticker (not just the configured default)
    to a security_id via its TICKER identifier."""
    stmt = (
        select(SecurityIdentifier.security_id)
        .where(
            SecurityIdentifier.identifier_type == "TICKER",
            SecurityIdentifier.identifier_value == ticker,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


@router.get("/beta/{security_id}", response_model=BetaResponse)
async def get_beta(
    security_id: uuid.UUID,
    benchmark: str = Query(default="SPY", description="Benchmark ticker"),
    session: AsyncSession = Depends(get_session),
):
    """Beta vs the requested benchmark, computed live from EOD prices.

    Uses the QuantEngine's OLS of security returns against the requested
    benchmark ticker's returns when that ticker resolves to a known security;
    falls back to the configured default market benchmark (and reports that
    ticker in the response instead of just echoing the input) when it
    doesn't. Degrades to ``None`` when no benchmark's price history loads —
    no fabricated fallback value.
    """
    await _resolve_security(session, security_id)

    benchmark_id = await _resolve_benchmark_security_id(session, benchmark)
    if benchmark_id is not None:
        benchmark_used = benchmark
    else:
        benchmark_id = await _find_benchmark_security_id(session)
        benchmark_used = settings.ANALYTICS_MARKET_BENCHMARK_TICKER
    outputs = await _quant_engine.compute(session, security_id, benchmark_id=benchmark_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return BetaResponse(
        security_id=security_id,
        beta=out_map.get("beta_market"),
        beta_blume_adjusted=out_map.get("beta_blume_adjusted"),
        r_squared=out_map.get("beta_r_squared"),
        benchmark=benchmark_used,
    )


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

@router.get("/drawdown/{security_id}", response_model=DrawdownResponse)
async def get_drawdown(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Max drawdown analysis."""
    sec = await _resolve_security(session, security_id)
    outputs = await _engine.compute(session, security_id)
    out_map = {o.metric_name: o.value for o in outputs}

    risk_level = RiskEngine.classify_risk_level(out_map.get("var_historical_95_1d"))

    return DrawdownResponse(
        security_id=security_id,
        max_drawdown=out_map.get("max_drawdown"),
        annualized_volatility=out_map.get("annualized_volatility"),
        risk_level=risk_level,
    )
