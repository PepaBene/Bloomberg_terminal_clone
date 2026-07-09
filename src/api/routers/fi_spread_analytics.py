"""Pillar 2 FI Supplement — Part 3: Spread Analytics API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.bond_analytics import compute_modified_duration, compute_ytm
from src.engines.e11_spread_analytics import (
    compute_breakeven_spread,
    compute_g_spread_interpolated,
    compute_oas_simplified,
    compute_relative_value,
    compute_spread_duration,
    compute_z_spread,
)
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.yield_curve import YieldCurveSnapshot
from src.schemas.fi_spread_analytics import (
    BreakevenResponse,
    RelativeValueResponse,
    SpreadAnalyticsResponse,
    SpreadHistoryItem,
    SpreadHistoryResponse,
    SpreadScreenItem,
    SpreadScreenRequest,
    SpreadScreenResponse,
)

router = APIRouter(prefix="/v2/analytics", tags=["FI Spread Analytics"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_bond(session: AsyncSession, cusip: str) -> CorporateBond:
    """Fetch a CorporateBond by CUSIP or raise 404."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with CUSIP {cusip} not found")
    return bond


# Standard curve tenor columns: (par_rate_col, zero_rate_col, tenor_years)
_CURVE_TENORS = [
    ("rate_1m", "zero_1m", 0.0833),
    ("rate_3m", "zero_3m", 0.25),
    ("rate_6m", "zero_6m", 0.5),
    ("rate_1y", "zero_1y", 1.0),
    ("rate_2y", "zero_2y", 2.0),
    ("rate_3y", "zero_3y", 3.0),
    ("rate_5y", "zero_5y", 5.0),
    ("rate_7y", "zero_7y", 7.0),
    ("rate_10y", "zero_10y", 10.0),
    ("rate_20y", "zero_20y", 20.0),
    ("rate_30y", "zero_30y", 30.0),
]


async def _get_latest_treasury_curve(
    session: AsyncSession,
) -> tuple[list[dict] | None, list[dict] | None]:
    """Fetch the latest TREASURY_NOMINAL snapshot as (par_curve, zero_curve).

    par_curve items:  {tenor_years, yield_rate}  (decimal, e.g. 0.045)
    zero_curve items: {tenor_years, zero_rate}   (decimal)
    Returns (None, None) if no snapshot exists.
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

    par: list[dict] = []
    zero: list[dict] = []
    for rate_col, zero_col, tenor_years in _CURVE_TENORS:
        rate_val = getattr(snapshot, rate_col, None)
        if rate_val is not None:
            par.append({"tenor_years": tenor_years, "yield_rate": float(rate_val)})
        zero_val = getattr(snapshot, zero_col, None)
        if zero_val is not None:
            zero.append({"tenor_years": tenor_years, "zero_rate": float(zero_val)})

    return (par or None), (zero or None)


def _bond_cashflows(
    coupon_rate: float,
    frequency: int,
    years_to_maturity: float,
    face_value: float = 100.0,
) -> list[dict]:
    """Generate a bullet bond's cash flows as [{years, amount}].

    Coupons of coupon_rate*face/frequency at each period, plus face at maturity.
    """
    if frequency <= 0 or years_to_maturity <= 0:
        return [{"years": max(years_to_maturity, 0.0), "amount": face_value}]

    coupon = coupon_rate * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    cash_flows: list[dict] = []
    for k in range(1, n_periods + 1):
        amount = coupon + (face_value if k == n_periods else 0.0)
        cash_flows.append({"years": k / frequency, "amount": amount})
    return cash_flows


async def _get_eod_prices(
    session: AsyncSession, bond: CorporateBond
) -> list[BondEODPrice]:
    """Get all EOD price records for a bond, ordered by date descending."""
    query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


# ── 1. GET /bonds/{cusip}/spreads ────────────────────────────────────


@router.get(
    "/bonds/{cusip}/spreads",
    response_model=SpreadAnalyticsResponse,
)
async def get_spreads(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get spread analytics for a bond (G-spread from latest EOD, computed spread duration)."""
    bond = await _get_bond(session, cusip)

    # Get latest EOD price
    query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    latest_price = result.scalar_one_or_none()

    g_spread_bps: int | None = None
    z_spread_bps: int | None = None
    oas_bps: int | None = None
    spread_dur: float | None = None
    treasury_benchmark_maturity: float | None = None

    if latest_price is not None:
        # Fall back to the stored G-spread if we cannot compute one below.
        g_spread_bps = latest_price.g_spread_bps

        # Compute modified duration for spread duration
        coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
        freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
        today = date.today()
        years_to_maturity = max(0.0, (bond.maturity_date - today).days / 365.25)
        treasury_benchmark_maturity = round(years_to_maturity, 2)

        if years_to_maturity > 0 and latest_price.last_trade_price is not None:
            price_val = float(latest_price.last_trade_price)
            ytm = compute_ytm(price_val, coupon, 100.0, years_to_maturity, freq)
            mod_dur = compute_modified_duration(ytm, coupon, years_to_maturity, freq)
            spread_dur = round(compute_spread_duration(mod_dur), 4)

            # Fetch the latest treasury curve to compute real spreads.
            par_curve, zero_curve = await _get_latest_treasury_curve(session)

            # G-spread = bond YTM - interpolated treasury par yield at the bond's
            # exact maturity. Computed from the curve rather than passed through.
            if par_curve:
                g_spread_bps = compute_g_spread_interpolated(
                    ytm, years_to_maturity, par_curve
                )

            # Z-spread = constant spread over the zero curve that reprices the
            # bond's cash flows to its market price (Newton-Raphson).
            if zero_curve:
                cash_flows = _bond_cashflows(coupon, freq, years_to_maturity)
                z_spread_bps = compute_z_spread(cash_flows, price_val, zero_curve)

                # OAS: for bonds with NO embedded optionality, the option cost is
                # zero, so OAS == Z-spread (an exact identity, not an estimate).
                # For callable/puttable bonds a real option-adjusted computation
                # requires a short-rate/option model, which does not exist in this
                # codebase, so OAS is left null rather than fabricated.
                if not bond.is_callable and not bond.is_puttable:
                    oas_bps = compute_oas_simplified(z_spread_bps, option_cost_bps=0)

    return SpreadAnalyticsResponse(
        cusip=cusip,
        g_spread_bps=g_spread_bps,
        z_spread_bps=z_spread_bps,
        oas_bps=oas_bps,
        spread_duration=spread_dur,
        treasury_benchmark_maturity=treasury_benchmark_maturity,
    )


# ── 2. GET /bonds/{cusip}/spreads/history ────────────────────────────


@router.get(
    "/bonds/{cusip}/spreads/history",
    response_model=SpreadHistoryResponse,
)
async def get_spread_history(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get spread history for a bond from BondEODPrice records."""
    bond = await _get_bond(session, cusip)

    query = (
        select(BondEODPrice)
        .where(
            BondEODPrice.bond_id == bond.bond_id,
            BondEODPrice.g_spread_bps.isnot(None),
        )
        .order_by(BondEODPrice.price_date.asc())
    )

    if start:
        query = query.where(BondEODPrice.price_date >= start)
    if end:
        query = query.where(BondEODPrice.price_date <= end)

    result = await session.execute(query)
    items = result.scalars().all()

    history = [
        SpreadHistoryItem(
            price_date=eod.price_date,
            g_spread_bps=eod.g_spread_bps,
            z_spread_bps=None,
        )
        for eod in items
    ]

    return SpreadHistoryResponse(cusip=cusip, history=history)


# ── 3. GET /bonds/{cusip}/relative-value ─────────────────────────────


@router.get(
    "/bonds/{cusip}/relative-value",
    response_model=RelativeValueResponse,
)
async def get_relative_value(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Relative value analysis vs own history and peers (same seniority/IG status)."""
    bond = await _get_bond(session, cusip)
    eod_prices = await _get_eod_prices(session, bond)

    if not eod_prices:
        raise HTTPException(
            status_code=404, detail=f"No price data for bond {cusip}"
        )

    # Get latest spread
    latest = eod_prices[0]
    if latest.g_spread_bps is None:
        raise HTTPException(
            status_code=404,
            detail=f"No G-spread available for bond {cusip}",
        )

    current_spread = float(latest.g_spread_bps)

    # Historical spreads for this bond
    historical_spreads = [
        float(p.g_spread_bps) for p in eod_prices if p.g_spread_bps is not None
    ]

    # Peer spreads: same seniority and IG status, latest EOD g_spread_bps
    peer_spreads: list[float] = []
    peer_query = (
        select(CorporateBond.bond_id)
        .where(
            CorporateBond.cusip != cusip,
            CorporateBond.seniority == bond.seniority,
            CorporateBond.is_investment_grade == bond.is_investment_grade,
        )
    )
    peer_result = await session.execute(peer_query)
    peer_bond_ids = [row[0] for row in peer_result.all()]

    if peer_bond_ids:
        # Get latest g_spread_bps for each peer (use the most recent EOD per bond)
        for pid in peer_bond_ids[:50]:  # cap at 50 peers for performance
            q = (
                select(BondEODPrice.g_spread_bps)
                .where(
                    BondEODPrice.bond_id == pid,
                    BondEODPrice.g_spread_bps.isnot(None),
                )
                .order_by(BondEODPrice.price_date.desc())
                .limit(1)
            )
            r = await session.execute(q)
            row = r.scalar_one_or_none()
            if row is not None:
                peer_spreads.append(float(row))

    rv = compute_relative_value(
        current_spread_bps=current_spread,
        historical_spreads=historical_spreads,
        peer_spreads=peer_spreads if peer_spreads else None,
        sector_spread_bps=None,
    )

    # Determine assessment label
    score = rv["rich_cheap_score"]
    if score <= -30:
        assessment = "RICH"
    elif score >= 30:
        assessment = "CHEAP"
    else:
        assessment = "FAIR"

    return RelativeValueResponse(
        cusip=cusip,
        current_spread_bps=current_spread,
        own_percentile=rv["own_percentile"],
        own_z_score=rv["own_z_score"],
        vs_peers_percentile=rv["vs_peers_percentile"],
        vs_sector_diff_bps=rv["vs_sector_diff_bps"],
        rich_cheap_score=rv["rich_cheap_score"],
        assessment=assessment,
    )


# ── 4. GET /bonds/{cusip}/breakeven ──────────────────────────────────


@router.get(
    "/bonds/{cusip}/breakeven",
    response_model=BreakevenResponse,
)
async def get_breakeven(
    cusip: str,
    horizon_years: float = Query(1.0, description="Investment horizon in years"),
    session: AsyncSession = Depends(get_session),
):
    """Breakeven spread analysis for a bond."""
    bond = await _get_bond(session, cusip)

    # Get latest EOD price
    query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    latest_price = result.scalar_one_or_none()

    if latest_price is None:
        raise HTTPException(
            status_code=404, detail=f"No price data for bond {cusip}"
        )
    if latest_price.g_spread_bps is None:
        raise HTTPException(
            status_code=404,
            detail=f"No G-spread available for bond {cusip}",
        )

    spread = float(latest_price.g_spread_bps)

    # Compute modified duration
    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    today = date.today()
    years_to_maturity = max(0.0, (bond.maturity_date - today).days / 365.25)

    if years_to_maturity <= 0 or latest_price.last_trade_price is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot compute breakeven for matured bond {cusip}",
        )

    price_val = float(latest_price.last_trade_price)
    ytm = compute_ytm(price_val, coupon, 100.0, years_to_maturity, freq)
    mod_dur = compute_modified_duration(ytm, coupon, years_to_maturity, freq)

    be = compute_breakeven_spread(spread, mod_dur, horizon_years)

    return BreakevenResponse(
        cusip=cusip,
        spread_bps=spread,
        modified_duration=round(mod_dur, 4),
        carry_bps=be["carry_bps"],
        breakeven_widening_bps=be["breakeven_widening_bps"],
        horizon_years=be["horizon_years"],
    )


# ── 5. POST /bonds/spread-screen ────────────────────────────────────


@router.post(
    "/bonds/spread-screen",
    response_model=SpreadScreenResponse,
)
async def spread_screen(
    body: SpreadScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Multi-factor spread screening across all bonds."""
    # Get all bonds with their latest EOD spread
    bond_query = select(CorporateBond).where(
        CorporateBond.status == "OUTSTANDING"
    )
    bond_result = await session.execute(bond_query)
    bonds = bond_result.scalars().unique().all()

    results: list[SpreadScreenItem] = []

    for bond in bonds:
        # Get latest g_spread_bps
        eod_q = (
            select(BondEODPrice)
            .where(
                BondEODPrice.bond_id == bond.bond_id,
                BondEODPrice.g_spread_bps.isnot(None),
            )
            .order_by(BondEODPrice.price_date.desc())
            .limit(1)
        )
        eod_result = await session.execute(eod_q)
        latest_eod = eod_result.scalar_one_or_none()

        if latest_eod is None:
            continue

        g_spread = latest_eod.g_spread_bps

        # Apply spread filters
        if body.min_spread_bps is not None and g_spread < body.min_spread_bps:
            continue
        if body.max_spread_bps is not None and g_spread > body.max_spread_bps:
            continue

        # Compute relative value if percentile or rich/cheap filters are requested
        own_percentile: float | None = None
        rich_cheap_score: float | None = None

        needs_rv = (
            body.min_percentile is not None
            or body.max_percentile is not None
            or body.min_rich_cheap is not None
            or body.max_rich_cheap is not None
        )

        if needs_rv:
            # Get historical spreads for this bond
            hist_q = select(BondEODPrice.g_spread_bps).where(
                BondEODPrice.bond_id == bond.bond_id,
                BondEODPrice.g_spread_bps.isnot(None),
            )
            hist_result = await session.execute(hist_q)
            hist_spreads = [float(r[0]) for r in hist_result.all()]

            if hist_spreads:
                rv = compute_relative_value(
                    current_spread_bps=float(g_spread),
                    historical_spreads=hist_spreads,
                )
                own_percentile = rv["own_percentile"]
                rich_cheap_score = rv["rich_cheap_score"]
            else:
                continue

            # Apply percentile filters
            if body.min_percentile is not None and own_percentile < body.min_percentile:
                continue
            if body.max_percentile is not None and own_percentile > body.max_percentile:
                continue
            if body.min_rich_cheap is not None and rich_cheap_score < body.min_rich_cheap:
                continue
            if body.max_rich_cheap is not None and rich_cheap_score > body.max_rich_cheap:
                continue

        results.append(
            SpreadScreenItem(
                cusip=bond.cusip,
                name=bond.name,
                g_spread_bps=g_spread,
                own_percentile=own_percentile,
                rich_cheap_score=rich_cheap_score,
            )
        )

        if len(results) >= body.limit:
            break

    return SpreadScreenResponse(results=results, total=len(results))
