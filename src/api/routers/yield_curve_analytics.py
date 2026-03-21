"""Yield Curve Analytics API endpoints (Pillar 2 Supplement – Part 1)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.yield_curve_analytics import (
    compute_breakeven_inflation,
    compute_curve_analytics,
    interpolate_rate,
    nelson_siegel_fit,
    shift_curve,
    STANDARD_TENORS,
)
from src.models.yield_curve import YieldCurveSnapshot
from src.models.yield_curve_analytics import CurveAnalytics, YieldCurveFitted
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.yield_curve_analytics import (
    CurveAnalyticsResponse,
    CurveScenarioRequest,
    CurveScenarioResponse,
    CurveSpreadHistoryPointResponse,
    CurveSpreadHistoryResponse,
    FittedCurvePointResponse,
    FittedCurveResponse,
    NelsonSiegelParamsResponse,
    RiskFreeRateResponse,
    ShiftedCurvePointResponse,
)

router = APIRouter(tags=["Yield Curve Analytics"])

# ---------- Helpers ----------

_TENOR_MAP = {
    "rate_1m": 0.083,
    "rate_3m": 0.25,
    "rate_6m": 0.5,
    "rate_1y": 1.0,
    "rate_2y": 2.0,
    "rate_3y": 3.0,
    "rate_5y": 5.0,
    "rate_7y": 7.0,
    "rate_10y": 10.0,
    "rate_20y": 20.0,
    "rate_30y": 30.0,
}

_TENOR_PARSE = {
    "1M": 0.083, "3M": 0.25, "6M": 0.5,
    "1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "5Y": 5.0,
    "7Y": 7.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0,
}


def _snapshot_to_tenors_rates(snapshot: YieldCurveSnapshot) -> tuple[list[float], list[float]]:
    """Extract tenors and rates from a YieldCurveSnapshot row."""
    tenors: list[float] = []
    rates: list[float] = []
    for col_name, tenor in sorted(_TENOR_MAP.items(), key=lambda x: x[1]):
        value = getattr(snapshot, col_name, None)
        if value is not None:
            tenors.append(tenor)
            rates.append(float(value))
    return tenors, rates


def _parse_tenor(tenor_str: str) -> float:
    """Parse a tenor string like '10Y' or '3M' into years."""
    key = tenor_str.upper().strip()
    if key in _TENOR_PARSE:
        return _TENOR_PARSE[key]
    # Try bare float
    try:
        return float(key)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tenor format: {tenor_str}. Use e.g. '10Y', '3M', or a numeric year value.",
        )


async def _get_latest_snapshot(
    session: AsyncSession,
    curve_date: date | None = None,
    curve_type: str = "TREASURY_NOMINAL",
) -> YieldCurveSnapshot:
    """Fetch the latest (or date-specific) yield curve snapshot."""
    query = (
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == curve_type.upper())
        .order_by(YieldCurveSnapshot.curve_date.desc())
    )
    if curve_date:
        query = query.where(YieldCurveSnapshot.curve_date == curve_date)
    query = query.limit(1)

    result = await session.execute(query)
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No yield curve data found")
    return snapshot


# ---------- Endpoints ----------


@router.get(
    "/analytics/yield-curve",
    response_model=FittedCurveResponse,
)
async def get_fitted_curve(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
    method: str = Query("NELSON_SIEGEL", description="Fitting method: NELSON_SIEGEL, LINEAR, CUBIC_SPLINE"),
):
    """Return the fitted yield curve — uses cached fit if available, otherwise computes on the fly."""
    # Check for cached fit
    cached_query = (
        select(YieldCurveFitted)
        .where(
            YieldCurveFitted.curve_type == curve_type.upper(),
            YieldCurveFitted.method == method.upper(),
        )
        .order_by(YieldCurveFitted.curve_date.desc())
    )
    if curve_date:
        cached_query = cached_query.where(YieldCurveFitted.curve_date == curve_date)
    cached_query = cached_query.limit(1)

    result = await session.execute(cached_query)
    cached = result.scalar_one_or_none()

    if cached:
        # Build response from cached data
        points = []
        if cached.fitted_rates:
            for t_str, r in sorted(cached.fitted_rates.items(), key=lambda x: float(x[0])):
                points.append(FittedCurvePointResponse(tenor_years=float(t_str), fitted_rate=float(r)))

        params = None
        if cached.beta0 is not None:
            params = NelsonSiegelParamsResponse(
                beta0=float(cached.beta0),
                beta1=float(cached.beta1),
                beta2=float(cached.beta2),
                tau=float(cached.tau),
                fit_error=float(cached.fit_error) if cached.fit_error else 0.0,
            )

        return FittedCurveResponse(
            fit_id=cached.fit_id,
            curve_date=cached.curve_date,
            curve_type=cached.curve_type,
            method=cached.method,
            params=params,
            points=points,
        )

    # No cache — compute from raw snapshot
    snapshot = await _get_latest_snapshot(session, curve_date, curve_type)
    tenors, rates = _snapshot_to_tenors_rates(snapshot)

    if len(tenors) < 3:
        raise HTTPException(status_code=422, detail="Insufficient rate data for curve fitting")

    if method.upper() == "NELSON_SIEGEL":
        fit = nelson_siegel_fit(tenors, rates)
        params = NelsonSiegelParamsResponse(
            beta0=fit["beta0"], beta1=fit["beta1"],
            beta2=fit["beta2"], tau=fit["tau"],
            fit_error=fit["fit_error"],
        )
        points = [
            FittedCurvePointResponse(tenor_years=float(t), fitted_rate=float(r))
            for t, r in sorted(fit["fitted_rates"].items())
        ]
    else:
        # LINEAR / CUBIC_SPLINE — just return interpolated points at standard tenors
        params = None
        points = []
        for t in STANDARD_TENORS:
            r = interpolate_rate(tenors, rates, t, method.upper())
            points.append(FittedCurvePointResponse(tenor_years=t, fitted_rate=round(r, 8)))

    return FittedCurveResponse(
        curve_date=snapshot.curve_date,
        curve_type=curve_type.upper(),
        method=method.upper(),
        params=params,
        points=points,
    )


@router.get(
    "/analytics/yield-curve/spreads",
    response_model=CurveAnalyticsResponse,
)
async def get_curve_spreads(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
):
    """Return key yield curve spread metrics (2s10s, 3m10y, steepness, curvature)."""
    # Check for cached analytics
    cached_query = (
        select(CurveAnalytics)
        .order_by(CurveAnalytics.curve_date.desc())
    )
    if curve_date:
        cached_query = cached_query.where(CurveAnalytics.curve_date == curve_date)
    cached_query = cached_query.limit(1)

    result = await session.execute(cached_query)
    cached = result.scalar_one_or_none()
    if cached:
        return CurveAnalyticsResponse.model_validate(cached)

    # Compute from raw snapshot
    snapshot = await _get_latest_snapshot(session, curve_date)
    tenors, rates = _snapshot_to_tenors_rates(snapshot)

    analytics = compute_curve_analytics(tenors, rates)
    return CurveAnalyticsResponse(
        curve_date=snapshot.curve_date,
        spread_2s10s=analytics["spread_2s10s"],
        spread_3m10y=analytics["spread_3m10y"],
        steepness=analytics["steepness"],
        curvature=analytics["curvature"],
        breakeven_5y=analytics["breakeven_5y"],
        breakeven_10y=analytics["breakeven_10y"],
        is_inverted=analytics["is_inverted"],
    )


@router.get(
    "/analytics/yield-curve/rate",
    response_model=RiskFreeRateResponse,
)
async def get_interpolated_rate(
    session: AsyncSession = Depends(get_session),
    tenor: str = Query(..., description="Tenor, e.g. '10Y', '3M', or numeric years"),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
    method: str = Query("LINEAR", description="Interpolation method: LINEAR or CUBIC_SPLINE"),
):
    """Return an interpolated risk-free rate at any tenor."""
    target_tenor = _parse_tenor(tenor)
    snapshot = await _get_latest_snapshot(session, curve_date, curve_type)
    tenors, rates = _snapshot_to_tenors_rates(snapshot)

    rate = interpolate_rate(tenors, rates, target_tenor, method.upper())

    return RiskFreeRateResponse(
        tenor_years=target_tenor,
        rate=round(rate, 8),
        curve_date=snapshot.curve_date,
        interpolation_method=method.upper(),
    )


@router.post(
    "/analytics/yield-curve/scenario",
    response_model=CurveScenarioResponse,
)
async def apply_curve_scenario(
    body: CurveScenarioRequest,
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Apply a scenario shift (parallel, steepener, flattener, custom) to the yield curve."""
    snapshot = await _get_latest_snapshot(session, curve_date, curve_type)
    tenors, rates = _snapshot_to_tenors_rates(snapshot)

    # Convert custom_shifts keys from string tenor to float
    custom_shifts_float = None
    if body.custom_shifts:
        custom_shifts_float = {}
        for k, v in body.custom_shifts.items():
            custom_shifts_float[_parse_tenor(k)] = v

    shifted = shift_curve(
        tenors, rates,
        shift_type=body.shift_type.upper(),
        shift_bps=body.shift_bps,
        custom_shifts=custom_shifts_float,
    )

    points = [ShiftedCurvePointResponse(**pt) for pt in shifted]
    return CurveScenarioResponse(
        shift_type=body.shift_type.upper(),
        shift_bps=body.shift_bps,
        points=points,
    )


@router.get(
    "/analytics/yield-curve/spreads/history",
    response_model=CurveSpreadHistoryResponse,
)
async def get_spread_history(
    session: AsyncSession = Depends(get_session),
    spread_type: str = Query("2s10s", description="Spread type: 2s10s, 3m10y"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
    limit: int = Query(252, ge=1, le=2520, description="Max points"),
):
    """Return historical spread time series from cached analytics or raw snapshots."""
    # Map spread_type to column
    spread_col_map = {
        "2s10s": "spread_2s10s",
        "3m10y": "spread_3m10y",
    }
    spread_key = spread_type.lower()
    if spread_key not in spread_col_map:
        raise HTTPException(status_code=400, detail=f"Invalid spread_type: {spread_type}. Use '2s10s' or '3m10y'.")

    col_name = spread_col_map[spread_key]

    # Try CurveAnalytics first
    query = select(CurveAnalytics).order_by(CurveAnalytics.curve_date.desc())
    if start:
        query = query.where(CurveAnalytics.curve_date >= start)
    if end:
        query = query.where(CurveAnalytics.curve_date <= end)
    query = query.limit(limit)

    result = await session.execute(query)
    rows = result.scalars().all()

    if rows:
        points = []
        for row in reversed(rows):  # chronological order
            val = getattr(row, col_name, None)
            if val is not None:
                points.append(CurveSpreadHistoryPointResponse(
                    curve_date=row.curve_date,
                    spread_value=float(val),
                ))
        return CurveSpreadHistoryResponse(spread_type=spread_key, points=points)

    # Fallback: compute from YieldCurveSnapshot
    snap_query = (
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == "TREASURY_NOMINAL")
        .order_by(YieldCurveSnapshot.curve_date.desc())
    )
    if start:
        snap_query = snap_query.where(YieldCurveSnapshot.curve_date >= start)
    if end:
        snap_query = snap_query.where(YieldCurveSnapshot.curve_date <= end)
    snap_query = snap_query.limit(limit)

    snap_result = await session.execute(snap_query)
    snapshots = snap_result.scalars().all()

    points = []
    for snap in reversed(snapshots):
        # Read spread directly from snapshot columns if available
        val = getattr(snap, col_name, None)
        if val is not None:
            points.append(CurveSpreadHistoryPointResponse(
                curve_date=snap.curve_date,
                spread_value=float(val),
            ))
        else:
            # Compute on the fly
            tenors, rates = _snapshot_to_tenors_rates(snap)
            analytics = compute_curve_analytics(tenors, rates)
            spread_val = analytics.get(col_name)
            if spread_val is not None:
                points.append(CurveSpreadHistoryPointResponse(
                    curve_date=snap.curve_date,
                    spread_value=float(spread_val),
                ))

    return CurveSpreadHistoryResponse(spread_type=spread_key, points=points)


@router.get(
    "/analytics/yield-curve/fitted",
    response_model=FittedCurveResponse,
)
async def get_nelson_siegel_params(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return Nelson-Siegel fitted parameters for a date (computes if not cached)."""
    # Check cached
    cached_query = (
        select(YieldCurveFitted)
        .where(
            YieldCurveFitted.curve_type == curve_type.upper(),
            YieldCurveFitted.method == "NELSON_SIEGEL",
        )
        .order_by(YieldCurveFitted.curve_date.desc())
    )
    if curve_date:
        cached_query = cached_query.where(YieldCurveFitted.curve_date == curve_date)
    cached_query = cached_query.limit(1)

    result = await session.execute(cached_query)
    cached = result.scalar_one_or_none()

    if cached:
        points = []
        if cached.fitted_rates:
            for t_str, r in sorted(cached.fitted_rates.items(), key=lambda x: float(x[0])):
                points.append(FittedCurvePointResponse(tenor_years=float(t_str), fitted_rate=float(r)))

        return FittedCurveResponse(
            fit_id=cached.fit_id,
            curve_date=cached.curve_date,
            curve_type=cached.curve_type,
            method=cached.method,
            params=NelsonSiegelParamsResponse(
                beta0=float(cached.beta0),
                beta1=float(cached.beta1),
                beta2=float(cached.beta2),
                tau=float(cached.tau),
                fit_error=float(cached.fit_error) if cached.fit_error else 0.0,
            ),
            points=points,
        )

    # Compute from raw snapshot
    snapshot = await _get_latest_snapshot(session, curve_date, curve_type)
    tenors, rates = _snapshot_to_tenors_rates(snapshot)

    if len(tenors) < 3:
        raise HTTPException(status_code=422, detail="Insufficient rate data for Nelson-Siegel fitting")

    fit = nelson_siegel_fit(tenors, rates)
    points = [
        FittedCurvePointResponse(tenor_years=float(t), fitted_rate=float(r))
        for t, r in sorted(fit["fitted_rates"].items())
    ]

    return FittedCurveResponse(
        curve_date=snapshot.curve_date,
        curve_type=curve_type.upper(),
        method="NELSON_SIEGEL",
        params=NelsonSiegelParamsResponse(
            beta0=fit["beta0"], beta1=fit["beta1"],
            beta2=fit["beta2"], tau=fit["tau"],
            fit_error=fit["fit_error"],
        ),
        points=points,
    )
