"""Pillar 2 FI Supplement – Part 2: Duration & Convexity Analytics API."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.bond_analytics import (
    compute_convexity,
    compute_macaulay_duration,
    compute_modified_duration,
    compute_ytm,
)
from src.engines.e10_duration import (
    compute_dv01,
    compute_effective_convexity,
    compute_effective_duration,
    compute_key_rate_durations,
    compute_portfolio_duration,
    generate_rate_sensitivity_table,
)
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.yield_curve import YieldCurveSnapshot
from src.schemas.fi_duration import (
    DurationHistoryItem,
    DurationHistoryResponse,
    DurationResponse,
    KeyRateDurationResponse,
    PortfolioDurationRequest,
    PortfolioDurationResponse,
    RateSensitivityItem,
    RateSensitivityResponse,
)

router = APIRouter(prefix="/v2/analytics", tags=["Fixed Income - Duration Analytics"])


# Standard zero-curve tenor columns: (zero_rate_col, tenor_years)
_ZERO_TENORS = [
    ("zero_1m", 0.0833),
    ("zero_3m", 0.25),
    ("zero_6m", 0.5),
    ("zero_1y", 1.0),
    ("zero_2y", 2.0),
    ("zero_3y", 3.0),
    ("zero_5y", 5.0),
    ("zero_7y", 7.0),
    ("zero_10y", 10.0),
    ("zero_20y", 20.0),
    ("zero_30y", 30.0),
]


async def _get_latest_zero_curve(
    session: AsyncSession,
) -> tuple[list[dict] | None, date | None]:
    """Fetch the latest TREASURY_NOMINAL zero curve as [{tenor_years, zero_rate}].

    Returns (None, None) if no snapshot with zero rates exists.
    """
    query = (
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == "TREASURY_NOMINAL")
        .order_by(YieldCurveSnapshot.curve_date.desc())
        .limit(1)
    )
    snapshot = (await session.execute(query)).scalar_one_or_none()
    if snapshot is None:
        return None, None

    zero: list[dict] = []
    for zero_col, tenor_years in _ZERO_TENORS:
        zero_val = getattr(snapshot, zero_col, None)
        if zero_val is not None:
            zero.append({"tenor_years": tenor_years, "zero_rate": float(zero_val)})

    return (zero or None), snapshot.curve_date


# ── 1. GET /v2/analytics/bonds/{cusip}/duration ──────────────────────


@router.get(
    "/bonds/{cusip}/duration",
    response_model=DurationResponse,
)
async def get_duration(
    cusip: str,
    price: float | None = Query(None, description="Override market price (% of par)"),
    session: AsyncSession = Depends(get_session),
):
    """Compute all duration metrics for a bond by CUSIP.

    If price is not provided, the latest EOD price is used.
    """
    # Look up the bond
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    # Resolve price
    bond_price = price
    if bond_price is None:
        eod_query = (
            select(BondEODPrice)
            .where(BondEODPrice.bond_id == bond.bond_id)
            .order_by(BondEODPrice.price_date.desc())
            .limit(1)
        )
        eod_result = await session.execute(eod_query)
        eod = eod_result.scalars().first()
        if eod and eod.last_trade_price is not None:
            bond_price = float(eod.last_trade_price)
        else:
            bond_price = 100.0  # assume par if no price available

    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2

    today = date.today()
    years_to_maturity = (bond.maturity_date - today).days / 365.25
    if years_to_maturity < 0:
        years_to_maturity = 0.0

    ytm = compute_ytm(bond_price, coupon, 100.0, years_to_maturity, freq)
    mac_dur = compute_macaulay_duration(ytm, coupon, years_to_maturity, freq)
    mod_dur = compute_modified_duration(ytm, coupon, years_to_maturity, freq)
    conv = compute_convexity(ytm, coupon, years_to_maturity, freq)
    dv01 = compute_dv01(mod_dur, bond_price)

    # Effective duration/convexity: compute only if callable
    eff_dur = None
    eff_conv = None
    if bond.is_callable:
        shock = 100.0  # 100 bps shock
        ytm_up = ytm + shock / 10000.0
        ytm_down = ytm - shock / 10000.0

        # Reprice with shifted yields using the simple present value formula
        p_up = _reprice_bond(coupon, 100.0, years_to_maturity, freq, ytm_up)
        p_down = _reprice_bond(coupon, 100.0, years_to_maturity, freq, ytm_down)

        eff_dur = compute_effective_duration(p_up, p_down, bond_price, shock)
        eff_conv = compute_effective_convexity(p_up, p_down, bond_price, shock)

    # Key rate durations: partial durations at 8 standard tenors, computed by
    # bumping each point of the treasury zero curve. Only available when a zero
    # curve snapshot exists.
    key_rate_durations = None
    if years_to_maturity > 0:
        zero_curve, _ = await _get_latest_zero_curve(session)
        if zero_curve:
            key_rate_durations = compute_key_rate_durations(
                price=bond_price,
                coupon_rate=coupon,
                face_value=100.0,
                years_to_maturity=years_to_maturity,
                frequency=freq,
                zero_curve=zero_curve,
            )

    return DurationResponse(
        cusip=cusip,
        macaulay_duration=round(mac_dur, 6),
        modified_duration=round(mod_dur, 6),
        dv01=round(dv01, 6),
        convexity=round(conv, 6),
        effective_duration=round(eff_dur, 6) if eff_dur is not None else None,
        effective_convexity=round(eff_conv, 6) if eff_conv is not None else None,
        key_rate_durations=key_rate_durations,
    )


# ── 1b. GET /v2/analytics/bonds/{cusip}/key-rate-durations ───────────


@router.get(
    "/bonds/{cusip}/key-rate-durations",
    response_model=KeyRateDurationResponse,
)
async def get_key_rate_durations(
    cusip: str,
    price: float | None = Query(None, description="Override market price (% of par)"),
    session: AsyncSession = Depends(get_session),
):
    """Compute Key Rate Durations (KRD) for a bond at 8 standard tenors.

    Each KRD measures the bond's price sensitivity to a 1bp bump at a single
    point on the treasury zero curve (holding all other points fixed). Requires
    a TREASURY_NOMINAL zero-coupon curve snapshot.
    """
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()
    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    # Resolve price (latest EOD, else par) — mirrors the duration endpoint.
    bond_price = price
    if bond_price is None:
        eod_query = (
            select(BondEODPrice)
            .where(BondEODPrice.bond_id == bond.bond_id)
            .order_by(BondEODPrice.price_date.desc())
            .limit(1)
        )
        eod = (await session.execute(eod_query)).scalars().first()
        if eod and eod.last_trade_price is not None:
            bond_price = float(eod.last_trade_price)
        else:
            bond_price = 100.0

    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    today = date.today()
    years_to_maturity = (bond.maturity_date - today).days / 365.25
    if years_to_maturity <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot compute key rate durations for matured bond {cusip}",
        )

    zero_curve, curve_date = await _get_latest_zero_curve(session)
    if not zero_curve:
        raise HTTPException(
            status_code=404,
            detail="No treasury zero-coupon curve available to compute key rate durations",
        )

    krd = compute_key_rate_durations(
        price=bond_price,
        coupon_rate=coupon,
        face_value=100.0,
        years_to_maturity=years_to_maturity,
        frequency=freq,
        zero_curve=zero_curve,
    )

    return KeyRateDurationResponse(
        cusip=cusip,
        curve_date=curve_date,
        key_rate_durations=krd,
        total_key_rate_duration=round(sum(krd.values()), 6),
    )


# ── 2. GET /v2/analytics/bonds/{cusip}/duration/history ──────────────


@router.get(
    "/bonds/{cusip}/duration/history",
    response_model=DurationHistoryResponse,
)
async def get_duration_history(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Modified duration over time from BondEODPrice records."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2

    eod_query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.asc())
    )
    eod_result = await session.execute(eod_query)
    eod_records = eod_result.scalars().all()

    if not eod_records:
        raise HTTPException(
            status_code=404,
            detail=f"No price history found for CUSIP {cusip}",
        )

    history: list[DurationHistoryItem] = []
    for eod in eod_records:
        eod_price = float(eod.last_trade_price) if eod.last_trade_price else 100.0
        pd = eod.price_date
        years_to_mat = (bond.maturity_date - pd).days / 365.25
        if years_to_mat < 0:
            years_to_mat = 0.0

        ytm = compute_ytm(eod_price, coupon, 100.0, years_to_mat, freq)
        mod_dur = compute_modified_duration(ytm, coupon, years_to_mat, freq)
        dv01 = compute_dv01(mod_dur, eod_price)

        history.append(
            DurationHistoryItem(
                price_date=pd,
                modified_duration=round(mod_dur, 6),
                dv01=round(dv01, 6),
            )
        )

    return DurationHistoryResponse(cusip=cusip, history=history)


# ── 3. POST /v2/analytics/bonds/portfolio/duration ───────────────────


@router.post(
    "/bonds/portfolio/duration",
    response_model=PortfolioDurationResponse,
)
async def portfolio_duration(
    body: PortfolioDurationRequest,
):
    """Compute portfolio-level duration analytics from a list of positions."""
    if not body.positions:
        raise HTTPException(status_code=422, detail="At least one position is required")

    positions_dicts = []
    for pos in body.positions:
        d = {
            "weight": pos.weight,
            "modified_duration": pos.modified_duration,
            "dv01": pos.dv01,
            "convexity": pos.convexity,
        }
        if pos.key_rate_durations:
            d["key_rate_durations"] = pos.key_rate_durations
        positions_dicts.append(d)

    result = compute_portfolio_duration(positions_dicts)

    return PortfolioDurationResponse(
        weighted_avg_duration=result["weighted_avg_duration"],
        portfolio_dv01=result["portfolio_dv01"],
        weighted_avg_convexity=result["weighted_avg_convexity"],
        portfolio_key_rate_durations=result.get("portfolio_key_rate_durations"),
        position_count=len(body.positions),
    )


# ── 4. POST /v2/analytics/bonds/{cusip}/rate-sensitivity ─────────────


@router.post(
    "/bonds/{cusip}/rate-sensitivity",
    response_model=RateSensitivityResponse,
)
async def rate_sensitivity(
    cusip: str,
    price: float | None = Query(None, description="Override market price (% of par)"),
    session: AsyncSession = Depends(get_session),
):
    """Compute price impact table for various yield shifts."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    bond_price = price
    if bond_price is None:
        eod_query = (
            select(BondEODPrice)
            .where(BondEODPrice.bond_id == bond.bond_id)
            .order_by(BondEODPrice.price_date.desc())
            .limit(1)
        )
        eod_result = await session.execute(eod_query)
        eod = eod_result.scalars().first()
        if eod and eod.last_trade_price is not None:
            bond_price = float(eod.last_trade_price)
        else:
            bond_price = 100.0

    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2

    today = date.today()
    years_to_maturity = (bond.maturity_date - today).days / 365.25
    if years_to_maturity < 0:
        years_to_maturity = 0.0

    ytm = compute_ytm(bond_price, coupon, 100.0, years_to_maturity, freq)
    mod_dur = compute_modified_duration(ytm, coupon, years_to_maturity, freq)
    conv = compute_convexity(ytm, coupon, years_to_maturity, freq)

    table = generate_rate_sensitivity_table(mod_dur, conv, bond_price)

    return RateSensitivityResponse(
        cusip=cusip,
        base_price=bond_price,
        modified_duration=round(mod_dur, 6),
        convexity=round(conv, 6),
        sensitivity=[
            RateSensitivityItem(
                shift_bps=row["shift_bps"],
                price_change_pct=row["price_change_pct"],
                estimated_new_price=row["estimated_new_price"],
            )
            for row in table
        ],
    )


# ── Helper ────────────────────────────────────────────────────────────


def _reprice_bond(
    coupon_rate: float,
    face_value: float,
    years_to_maturity: float,
    frequency: int,
    ytm: float,
) -> float:
    """Reprice a bond given a yield to maturity."""
    if frequency <= 0 or years_to_maturity <= 0:
        return face_value

    coupon = coupon_rate * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    y = ytm / frequency
    if y <= -1.0:
        y = 0.001

    pv = 0.0
    for t in range(1, n_periods + 1):
        df = (1 + y) ** (-t)
        pv += coupon * df
    pv += face_value * (1 + y) ** (-n_periods)

    return pv
