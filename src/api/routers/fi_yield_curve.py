"""Fixed Income Yield Curve API endpoints (D11 FI Supplement – Part 3)."""

import math
from datetime import date

from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.yield_curve_analytics import (
    compute_butterfly_spread,
    compute_spread_5s30s,
    interpolate_rate,
)
from src.models.yield_curve import YieldCurveSnapshot
from src.schemas.fi_yield_curve import (
    CurveHistoryPointResponse,
    CurveSurfacePointResponse,
    DiscountFactorInterpolatedResponse,
    EnhancedYieldCurveResponse,
    FIScenarioRequest,
    FIScenarioResponse,
    SpreadMetricsResponse,
    ZeroRateCurveResponse,
)

router = APIRouter(tags=["Fixed Income - Yield Curve"])


# ---------- Helpers ----------

_TENOR_MAP = {
    "rate_1m": ("1M", 0.083),
    "rate_3m": ("3M", 0.25),
    "rate_6m": ("6M", 0.5),
    "rate_1y": ("1Y", 1.0),
    "rate_2y": ("2Y", 2.0),
    "rate_3y": ("3Y", 3.0),
    "rate_5y": ("5Y", 5.0),
    "rate_7y": ("7Y", 7.0),
    "rate_10y": ("10Y", 10.0),
    "rate_20y": ("20Y", 20.0),
    "rate_30y": ("30Y", 30.0),
}

_TENOR_PARSE = {
    "1M": 0.083, "3M": 0.25, "6M": 0.5,
    "1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "5Y": 5.0,
    "7Y": 7.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0,
}

_ZERO_COLS = {
    "1M": "zero_1m", "3M": "zero_3m", "6M": "zero_6m",
    "1Y": "zero_1y", "2Y": "zero_2y", "3Y": "zero_3y",
    "5Y": "zero_5y", "7Y": "zero_7y", "10Y": "zero_10y",
    "20Y": "zero_20y", "30Y": "zero_30y",
}

_DF_COLS = {
    "1Y": "df_1y", "2Y": "df_2y", "5Y": "df_5y",
    "10Y": "df_10y", "20Y": "df_20y", "30Y": "df_30y",
}


async def _get_snapshot(
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


def _snapshot_par_rates(snapshot: YieldCurveSnapshot) -> dict[str, float]:
    """Extract par rates from a snapshot as {tenor_string: rate}."""
    par = {}
    for col_name, (tenor_str, _) in _TENOR_MAP.items():
        val = getattr(snapshot, col_name, None)
        if val is not None:
            par[tenor_str] = float(val)
    return par


def _rate_col_for_tenor(tenor: str) -> str:
    """Map a tenor string like '10Y' to the column name 'rate_10y'."""
    mapping = {ts: col for col, (ts, _) in _TENOR_MAP.items()}
    key = tenor.upper().strip()
    if key not in mapping:
        raise ValueError(f"Unknown tenor: {tenor}")
    return mapping[key]


# ---------- Endpoints (static routes first) ----------


@router.get(
    "/fixed-income/yield-curve/par",
    response_model=dict,
)
async def get_par_curve(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return par yield curve rates only."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)
    par = _snapshot_par_rates(snapshot)
    return {
        "curve_date": snapshot.curve_date.isoformat(),
        "curve_type": snapshot.curve_type,
        "par_rates": par,
    }


@router.get(
    "/fixed-income/yield-curve/zero",
    response_model=ZeroRateCurveResponse,
)
async def get_zero_curve(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return zero-coupon rate curve."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)
    zero_rates = {}
    for tenor_str, col_name in _ZERO_COLS.items():
        val = getattr(snapshot, col_name, None)
        if val is not None:
            zero_rates[tenor_str] = float(val)
    return ZeroRateCurveResponse(
        curve_date=snapshot.curve_date,
        curve_type=snapshot.curve_type,
        zero_rates=zero_rates,
    )


@router.get(
    "/fixed-income/yield-curve/spreads",
    response_model=SpreadMetricsResponse,
)
async def get_fi_spreads(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return all spread metrics including butterfly and 5s30s."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)
    return SpreadMetricsResponse(
        curve_date=snapshot.curve_date,
        spread_2s10s=float(snapshot.spread_2s10s) if snapshot.spread_2s10s is not None else None,
        spread_3m10y=float(snapshot.spread_3m10y) if snapshot.spread_3m10y is not None else None,
        spread_5s30s=float(snapshot.spread_5s30s) if snapshot.spread_5s30s is not None else None,
        butterfly_spread=float(snapshot.butterfly_spread) if snapshot.butterfly_spread is not None else None,
        is_inverted=snapshot.is_inverted,
    )


@router.get(
    "/fixed-income/yield-curve/history",
    response_model=list[CurveHistoryPointResponse],
)
async def get_curve_history(
    session: AsyncSession = Depends(get_session),
    tenor: str = Query("10Y", description="Tenor to track, e.g. '10Y', '2Y'"),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return time series of a specific tenor rate over a date range."""
    try:
        col_name = _rate_col_for_tenor(tenor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query = (
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == curve_type.upper())
        .order_by(YieldCurveSnapshot.curve_date.asc())
    )
    if start:
        query = query.where(YieldCurveSnapshot.curve_date >= start)
    if end:
        query = query.where(YieldCurveSnapshot.curve_date <= end)

    result = await session.execute(query)
    snapshots = result.scalars().all()

    points = []
    for snap in snapshots:
        val = getattr(snap, col_name, None)
        points.append(CurveHistoryPointResponse(
            curve_date=snap.curve_date,
            rate=float(val) if val is not None else None,
        ))
    return points


@router.get(
    "/fixed-income/yield-curve/surface",
    response_model=list[CurveSurfacePointResponse],
)
async def get_curve_surface(
    session: AsyncSession = Depends(get_session),
    months_back: int = Query(6, ge=1, le=60, description="Number of months of history"),
    tenors: str = Query("1M,3M,6M,1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y", description="Comma-separated tenors"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return 3D surface data: (date, tenor, rate) for visualization."""
    tenor_list = [t.strip().upper() for t in tenors.split(",")]
    cutoff = date.today() - relativedelta(months=months_back)

    query = (
        select(YieldCurveSnapshot)
        .where(
            YieldCurveSnapshot.curve_type == curve_type.upper(),
            YieldCurveSnapshot.curve_date >= cutoff,
        )
        .order_by(YieldCurveSnapshot.curve_date.asc())
    )
    result = await session.execute(query)
    snapshots = result.scalars().all()

    # Build mapping from tenor string to column name
    tenor_to_col = {ts: col for col, (ts, _) in _TENOR_MAP.items()}

    points = []
    for snap in snapshots:
        for t_str in tenor_list:
            col = tenor_to_col.get(t_str)
            if col:
                val = getattr(snap, col, None)
                points.append(CurveSurfacePointResponse(
                    curve_date=snap.curve_date,
                    tenor=t_str,
                    rate=float(val) if val is not None else None,
                ))
    return points


@router.get(
    "/fixed-income/yield-curve/discount-factor",
    response_model=DiscountFactorInterpolatedResponse,
)
async def get_discount_factor(
    session: AsyncSession = Depends(get_session),
    tenor_years: float = Query(..., description="Tenor in years for DF interpolation"),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return interpolated discount factor at a specific tenor."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)

    # Collect stored DFs
    df_tenors = []
    df_values = []
    df_tenor_years = {"1Y": 1.0, "2Y": 2.0, "5Y": 5.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0}
    for t_str, col in _DF_COLS.items():
        val = getattr(snapshot, col, None)
        if val is not None:
            df_tenors.append(df_tenor_years[t_str])
            df_values.append(float(val))

    if not df_tenors:
        raise HTTPException(status_code=404, detail="No discount factor data available")

    # Interpolate
    df_val = interpolate_rate(df_tenors, df_values, tenor_years)

    return DiscountFactorInterpolatedResponse(
        curve_date=snapshot.curve_date,
        tenor_years=tenor_years,
        discount_factor=round(df_val, 8),
    )


@router.post(
    "/fixed-income/yield-curve/scenario",
    response_model=FIScenarioResponse,
)
async def apply_fi_scenario(
    body: FIScenarioRequest,
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Apply a scenario shift to the par yield curve and return original + shifted rates."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)
    par = _snapshot_par_rates(snapshot)

    shift_delta = body.shift_bps / 10000.0
    shifted = {}

    for tenor_str, rate in par.items():
        t = _TENOR_PARSE.get(tenor_str, 5.0)
        if body.shift_type.upper() == "PARALLEL":
            delta = shift_delta
        elif body.shift_type.upper() == "STEEPENER":
            factor = (t - 5.0) / 25.0
            delta = factor * shift_delta
        elif body.shift_type.upper() == "FLATTENER":
            factor = (5.0 - t) / 25.0
            delta = factor * shift_delta
        else:
            delta = shift_delta

        shifted[tenor_str] = round(rate + delta, 6)

    return FIScenarioResponse(
        shift_type=body.shift_type.upper(),
        shift_bps=body.shift_bps,
        original_rates=par,
        shifted_rates=shifted,
    )


@router.get(
    "/fixed-income/yield-curve",
    response_model=EnhancedYieldCurveResponse,
)
async def get_enhanced_snapshot(
    session: AsyncSession = Depends(get_session),
    curve_date: date | None = Query(None, description="Specific date (defaults to latest)"),
    curve_type: str = Query("TREASURY_NOMINAL", description="Curve type"),
):
    """Return the full enhanced yield curve snapshot with all par, zero, DF, forward, NSV, and spread fields."""
    snapshot = await _get_snapshot(session, curve_date, curve_type)
    return EnhancedYieldCurveResponse.model_validate(snapshot)
