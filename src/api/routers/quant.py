"""Pillar 2: Quantitative Analytics API (Spec §9).

Endpoints for regression, correlation, stationarity, cointegration,
autocorrelation, and quantitative summary.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.config import settings
from src.engines.e2_wacc import _find_benchmark_security_id
from src.engines.e7_quant import QuantEngine, _load_price_series, _prices_to_returns
from src.models.security import Security
from src.schemas.quant import (
    AutocorrelationRequest,
    AutocorrelationResponse,
    CointegrationRequest,
    CointegrationResponse,
    CorrelationMatrixRequest,
    CorrelationMatrixResponse,
    CorrelationRequest,
    CorrelationResponse,
    QuantSummaryResponse,
    RegressionRequest,
    RegressionResponse,
    RollingRegressionPoint,
    RollingRegressionRequest,
    RollingRegressionResponse,
    StationarityRequest,
    StationarityResponse,
)
from src.schemas.risk import BetaResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Quantitative Analytics"])

_engine = QuantEngine()


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


async def _load_security_returns(
    session: AsyncSession, security_id: uuid.UUID, period_days: int = 756,
) -> list[float]:
    """Load returns for a security, raising 404 if not found."""
    await _resolve_security(session, security_id)
    _, prices = await _load_price_series(session, security_id, period_days)
    return _prices_to_returns(prices)


async def _resolve_independent_series(
    session: AsyncSession,
    independent_var: str,
    y_returns: list[float],
    period_days: int,
) -> tuple[list[float], list[float]]:
    """Resolve the regression independent variable to a real return series.

    Precedence:
      1. If ``independent_var`` is a security UUID, regress against that
         security's returns.
      2. If it names the market (``market_return``/``market``/``benchmark``),
         regress against the configured market benchmark's returns.
      3. Otherwise (or when the resolved series has too little overlapping
         data / the benchmark is not loaded) fall back to a plain time-index
         (0,1,2,...) trend regression — the original backward-compatible
         behaviour.

    Returns ``(x_returns, y_returns)`` trimmed to a common length.
    """
    x_source_id: uuid.UUID | None = None
    try:
        x_source_id = uuid.UUID(str(independent_var))
    except (ValueError, TypeError):
        if independent_var.lower() in ("market_return", "market", "benchmark"):
            x_source_id = await _find_benchmark_security_id(session)

    if x_source_id is not None:
        x_all = await _load_security_returns(session, x_source_id, period_days)
        min_len = min(len(x_all), len(y_returns))
        if min_len >= 30:
            return x_all[-min_len:], y_returns[-min_len:]

    # Fallback: plain time-index trend regression.
    return [float(i) for i in range(len(y_returns))], y_returns


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

@router.post("/regression", response_model=RegressionResponse)
async def run_regression(
    body: RegressionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run OLS regression."""
    if body.security_id is None:
        raise HTTPException(status_code=400, detail="security_id required")

    y_returns = await _load_security_returns(session, body.security_id, body.period_days)
    if len(y_returns) < 30:
        raise HTTPException(status_code=400, detail="Insufficient price data")

    # Resolve a real independent variable (benchmark or another security's
    # returns) when the caller provides one; fall back to a time-index trend
    # only when no meaningful independent series is available.
    indep_label = body.independent_vars[0] if body.independent_vars else "market_return"
    x_returns_f, y_returns = await _resolve_independent_series(
        session, indep_label, y_returns, body.period_days
    )

    result = await _engine.run_regression(
        session, body.security_id, x_returns_f, y_returns,
        method=body.method,
        dependent_var=body.dependent_var,
        independent_var=indep_label,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return RegressionResponse(
        regression_id=result.get("regression_id"),
        method=result["method"],
        coefficients=result["coefficients"],
        std_errors=result.get("std_errors"),
        r_squared=result.get("r_squared"),
        adj_r_squared=result.get("adj_r_squared"),
        f_statistic=result.get("f_statistic"),
        f_p_value=result.get("f_p_value"),
        n_observations=result["n_observations"],
        confidence_intervals=result.get("confidence_intervals"),
        residuals_summary=result.get("residuals_summary"),
    )


@router.post("/regression/rolling", response_model=RollingRegressionResponse)
async def run_rolling_regression(
    body: RollingRegressionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run rolling regression on a security."""
    y_returns = await _load_security_returns(session, body.security_id, body.period_days)
    x_returns, y_returns = await _resolve_independent_series(
        session, body.independent_var, y_returns, body.period_days
    )
    if len(y_returns) < body.window:
        raise HTTPException(status_code=400, detail="Insufficient data for window size")

    points = await _engine.run_rolling_regression(x_returns, y_returns, window=body.window)

    return RollingRegressionResponse(
        security_id=body.security_id,
        data_points=[
            RollingRegressionPoint(
                index=p["index"],
                beta=p["beta"],
                alpha=p["alpha"],
                r_squared=p["r_squared"],
            )
            for p in points
        ],
    )


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

@router.post("/correlation", response_model=CorrelationResponse)
async def run_correlation(
    body: CorrelationRequest,
    session: AsyncSession = Depends(get_session),
):
    """Pairwise correlation between two series."""
    try:
        x_id = uuid.UUID(body.series_x_id)
        y_id = uuid.UUID(body.series_y_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail="series_x_id/series_y_id must be valid UUIDs")

    x_returns = await _load_security_returns(session, x_id, body.period_days)
    y_returns = await _load_security_returns(session, y_id, body.period_days)

    min_len = min(len(x_returns), len(y_returns))
    if min_len < 10:
        raise HTTPException(status_code=400, detail="Insufficient data")
    if len(x_returns) != len(y_returns):
        logger.warning(
            "run_correlation: series length mismatch (x=%d, y=%d), truncating both to %d",
            len(x_returns), len(y_returns), min_len,
        )

    result = await _engine.run_correlation(
        session,
        x_returns[-min_len:],
        y_returns[-min_len:],
        method=body.method,
        series_x_id=body.series_x_id,
        series_y_id=body.series_y_id,
    )

    return CorrelationResponse(
        correlation_id=result.get("correlation_id"),
        method=result["method"],
        coefficient=result.get("coefficient"),
        p_value=result.get("p_value"),
        n_observations=result["n_observations"],
    )


@router.post("/correlation/matrix", response_model=CorrelationMatrixResponse)
async def run_correlation_matrix(
    body: CorrelationMatrixRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compute a full correlation matrix for multiple series."""
    from src.engines.e7_quant import _pearson_corr, _spearman_corr

    all_returns: list[list[float]] = []
    labels: list[str] = []
    for sid_str in body.series_ids:
        try:
            sid = uuid.UUID(sid_str)
        except (ValueError, TypeError):
            continue
        rets = await _load_security_returns(session, sid, body.period_days)
        if rets:
            all_returns.append(rets)
            labels.append(sid_str)

    n = len(all_returns)
    if n < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 series")

    # Trim to common length
    min_len = min(len(r) for r in all_returns)
    trimmed = [r[-min_len:] for r in all_returns]

    matrix: list[list[float | None]] = []
    p_matrix: list[list[float | None]] = []
    corr_fn = _spearman_corr if body.method == "SPEARMAN" else _pearson_corr
    for i in range(n):
        row_c: list[float | None] = []
        row_p: list[float | None] = []
        for j in range(n):
            if i == j:
                row_c.append(1.0)
                row_p.append(0.0)
            else:
                c, p = corr_fn(trimmed[i], trimmed[j])
                row_c.append(c)
                row_p.append(p)
        matrix.append(row_c)
        p_matrix.append(row_p)

    return CorrelationMatrixResponse(
        method=body.method,
        labels=labels,
        matrix=matrix,
        p_values=p_matrix,
    )


# ---------------------------------------------------------------------------
# Time Series
# ---------------------------------------------------------------------------

@router.post("/stationarity", response_model=StationarityResponse)
async def run_stationarity(
    body: StationarityRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run ADF or KPSS stationarity test."""
    if body.security_id is None:
        raise HTTPException(status_code=400, detail="security_id required")

    _, prices = await _load_price_series(session, body.security_id, body.period_days)
    if len(prices) < 30:
        raise HTTPException(status_code=400, detail="Insufficient data")

    result = await _engine.run_stationarity(
        session, prices, test_type=body.test_type,
        series_name=body.series_name,
        security_id=body.security_id,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Test failed or unsupported")

    return StationarityResponse(
        test_id=result.get("test_id"),
        test_type=body.test_type,
        series_name=body.series_name,
        test_statistic=result.get("test_statistic"),
        p_value=result.get("p_value"),
        critical_values=result.get("critical_values"),
        is_significant=result.get("is_significant", False),
        lags_used=result.get("lags_used"),
    )


@router.post("/cointegration", response_model=CointegrationResponse)
async def run_cointegration(
    body: CointegrationRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run Engle-Granger cointegration test."""
    try:
        x_id = uuid.UUID(body.series_x_id)
        y_id = uuid.UUID(body.series_y_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail="series_x_id/series_y_id must be valid UUIDs")

    _, x_prices = await _load_price_series(session, x_id, body.period_days)
    _, y_prices = await _load_price_series(session, y_id, body.period_days)

    if len(x_prices) < 30 or len(y_prices) < 30:
        raise HTTPException(status_code=400, detail="Insufficient data")
    if len(x_prices) != len(y_prices):
        logger.warning(
            "run_cointegration: series length mismatch (x=%d, y=%d)",
            len(x_prices), len(y_prices),
        )

    result = await _engine.run_cointegration(
        session, x_prices, y_prices,
        series_x_id=body.series_x_id, series_y_id=body.series_y_id,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="Cointegration test failed")

    return CointegrationResponse(
        test_id=result.get("test_id"),
        test_statistic=result.get("test_statistic"),
        p_value=result.get("p_value"),
        hedge_ratio=result.get("hedge_ratio"),
        is_cointegrated=result.get("is_cointegrated", False),
    )


@router.post("/autocorrelation", response_model=AutocorrelationResponse)
async def run_autocorrelation(
    body: AutocorrelationRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compute autocorrelation function at multiple lags."""
    from src.engines.e7_quant import _autocorrelation

    returns = await _load_security_returns(session, body.security_id, body.period_days)
    if len(returns) < 30:
        raise HTTPException(status_code=400, detail="Insufficient data")

    lags = list(range(1, body.max_lags + 1))
    acf_values = [_autocorrelation(returns, lag=lag) for lag in lags]

    return AutocorrelationResponse(
        security_id=body.security_id,
        lags=lags,
        acf_values=acf_values,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@router.get("/summary/{security_id}", response_model=QuantSummaryResponse)
async def get_quant_summary(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """All default quant metrics for a security, computed live on demand."""
    await _resolve_security(session, security_id)

    # Compute live (like the risk endpoints) rather than reading AnalyticsResult
    # rows that no batch job ever writes. Beta/correlation require a market
    # benchmark, resolved from the configured benchmark ticker.
    benchmark_id = await _find_benchmark_security_id(session)
    outputs = await _engine.compute(session, security_id, benchmark_id=benchmark_id)
    out_map = {o.metric_name: o.value for o in outputs}

    is_stat_val = out_map.get("is_stationary")
    is_stat = bool(is_stat_val) if is_stat_val is not None else None

    return QuantSummaryResponse(
        security_id=security_id,
        beta_market=out_map.get("beta_market"),
        beta_blume_adjusted=out_map.get("beta_blume_adjusted"),
        beta_rolling_60d=out_map.get("beta_rolling_60d"),
        correlation_market_pearson=out_map.get("correlation_market_pearson"),
        correlation_market_spearman=out_map.get("correlation_market_spearman"),
        autocorrelation_lag1=out_map.get("autocorrelation_lag1"),
        adf_test_statistic=out_map.get("adf_test_statistic"),
        adf_p_value=out_map.get("adf_p_value"),
        is_stationary=is_stat,
    )


@router.get("/beta/{security_id}", response_model=BetaResponse)
async def get_quant_beta(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Beta computed live from EOD prices vs the market benchmark."""
    await _resolve_security(session, security_id)

    benchmark_id = await _find_benchmark_security_id(session)
    outputs = await _engine.compute(session, security_id, benchmark_id=benchmark_id)
    out_map = {o.metric_name: o.value for o in outputs}

    return BetaResponse(
        security_id=security_id,
        beta=out_map.get("beta_market"),
        beta_blume_adjusted=out_map.get("beta_blume_adjusted"),
        r_squared=out_map.get("beta_r_squared"),
        benchmark=settings.ANALYTICS_MARKET_BENCHMARK_TICKER,
    )
