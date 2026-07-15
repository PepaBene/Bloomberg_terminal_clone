"""Pillar 2 FI Supplement -- Part 5: FI Risk Analytics endpoints."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.bond_analytics import (
    compute_convexity,
    compute_modified_duration,
    compute_ytm,
)
from src.engines.e12_fi_risk import (
    compute_credit_distribution,
    compute_credit_var,
    compute_expected_loss,
    compute_portfolio_dv01,
    compute_rate_scenario_pnl,
    compute_single_bond_risk,
    compute_spread_scenario_pnl,
)
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.schemas.fi_risk import (
    BondRiskMetricsResponse,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    PositionPnl,
    RateScenarioRequest,
    ScenarioPnlResponse,
    SpreadScenarioRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["FI Risk Analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_bond_by_cusip(cusip: str, session: AsyncSession) -> CorporateBond:
    """Look up a bond by CUSIP or raise 404."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with CUSIP {cusip} not found")
    return bond


def _positions_to_dicts(positions) -> list[dict]:
    """Convert list of PortfolioRiskPosition to list of dicts for engine functions."""
    return [p.model_dump() for p in positions]


async def _fill_missing_ratings(session: AsyncSession, pos_dicts: list[dict]) -> None:
    """Resolve rating_numeric from the DB for positions that gave a cusip but
    no rating — previously these endpoints trusted caller-supplied risk
    inputs exclusively and never looked up the bond record at all.
    """
    for pos in pos_dicts:
        if pos.get("rating_numeric") is not None or not pos.get("cusip"):
            continue
        result = await session.execute(
            select(CorporateBond).where(CorporateBond.cusip == pos["cusip"])
        )
        bond = result.scalars().unique().one_or_none()
        if bond is not None:
            pos["rating_numeric"] = _resolve_rating_numeric(bond)


async def _lookup_bond_duration_convexity(
    session: AsyncSession, cusip: str
) -> tuple[float, float] | None:
    """Compute a bond's real modified duration & convexity from its latest
    stored EOD price, mirroring ``get_bond_risk_metrics`` — used to backfill
    scenario inputs a caller left at their schema default instead of a real
    supplied value.
    """
    result = await session.execute(select(CorporateBond).where(CorporateBond.cusip == cusip))
    bond = result.scalars().unique().one_or_none()
    if bond is None:
        return None
    eod_result = await session.execute(
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    eod = eod_result.scalar_one_or_none()
    if eod is None:
        return None

    trade_price = float(eod.last_trade_price) if eod.last_trade_price is not None else 100.0
    coupon_rate = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    face = 100.0
    days_to_mat = (bond.maturity_date - eod.price_date).days
    years_to_mat = max(days_to_mat / 365.25, 0.01)

    ytm = compute_ytm(trade_price, coupon_rate, face, years_to_mat, freq)
    mod_dur = compute_modified_duration(ytm, coupon_rate, years_to_mat, freq)
    convexity = compute_convexity(ytm, coupon_rate, years_to_mat, freq)
    return mod_dur, convexity


# ---------------------------------------------------------------------------
# 1. POST /bonds/portfolio/risk
# ---------------------------------------------------------------------------


@router.post(
    "/bonds/portfolio/risk",
    response_model=PortfolioRiskResponse,
)
async def get_portfolio_risk(
    body: PortfolioRiskRequest,
    session: AsyncSession = Depends(get_session),
):
    """Portfolio risk summary: DV01, credit distribution, expected loss."""
    pos_dicts = _positions_to_dicts(body.positions)
    await _fill_missing_ratings(session, pos_dicts)

    portfolio_dv01 = compute_portfolio_dv01(pos_dicts)
    total_mv = sum(p.market_value for p in body.positions)
    credit_dist = compute_credit_distribution(pos_dicts)
    el_result = compute_expected_loss(pos_dicts)

    return PortfolioRiskResponse(
        portfolio_dv01=portfolio_dv01,
        total_market_value=total_mv,
        credit_distribution=credit_dist,
        expected_loss=el_result["total_expected_loss"],
        expected_loss_pct=el_result["total_expected_loss_pct"],
        position_count=len(body.positions),
    )


# ---------------------------------------------------------------------------
# 2. POST /bonds/portfolio/rate-scenario
# ---------------------------------------------------------------------------


@router.post(
    "/bonds/portfolio/rate-scenario",
    response_model=ScenarioPnlResponse,
)
async def get_rate_scenario(
    body: RateScenarioRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compute P&L from a parallel rate shift using duration-convexity approximation."""
    pos_dicts = _positions_to_dicts(body.positions)
    for pos in pos_dicts:
        # convexity left at the schema default (0.0) with a cusip supplied
        # means "not given" in practice -- look up the real bond convexity
        # instead of silently pricing the position as perfectly linear.
        if pos.get("convexity") == 0.0 and pos.get("cusip"):
            looked_up = await _lookup_bond_duration_convexity(session, pos["cusip"])
            if looked_up is not None:
                pos["convexity"] = looked_up[1]
    result = compute_rate_scenario_pnl(pos_dicts, body.rate_shift_bps)

    return ScenarioPnlResponse(
        total_pnl=result["total_pnl"],
        total_pnl_pct=result["total_pnl_pct"],
        shift_bps=body.rate_shift_bps,
        by_position=[
            PositionPnl(cusip=bp["cusip"], pnl=bp["pnl"], pnl_pct=bp["pnl_pct"])
            for bp in result["by_position"]
        ],
    )


# ---------------------------------------------------------------------------
# 3. POST /bonds/portfolio/spread-scenario
# ---------------------------------------------------------------------------


@router.post(
    "/bonds/portfolio/spread-scenario",
    response_model=ScenarioPnlResponse,
)
async def get_spread_scenario(
    body: SpreadScenarioRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compute P&L from a spread widening/tightening."""
    pos_dicts = _positions_to_dicts(body.positions)
    for pos in pos_dicts:
        if pos.get("spread_duration") is None and pos.get("cusip"):
            looked_up = await _lookup_bond_duration_convexity(session, pos["cusip"])
            if looked_up is not None:
                # Use modified duration as spread duration approximation,
                # same convention as get_bond_risk_metrics.
                pos["spread_duration"] = looked_up[0]
    result = compute_spread_scenario_pnl(pos_dicts, body.spread_shift_bps)

    return ScenarioPnlResponse(
        total_pnl=result["total_pnl"],
        total_pnl_pct=result["total_pnl_pct"],
        shift_bps=body.spread_shift_bps,
        by_position=[
            PositionPnl(cusip=bp["cusip"], pnl=bp["pnl"], pnl_pct=bp["pnl_pct"])
            for bp in result["by_position"]
        ],
    )


# ---------------------------------------------------------------------------
# 4. GET /bonds/{cusip}/risk-metrics
# ---------------------------------------------------------------------------


# Rating string -> numeric mapping
_RATING_MAP: dict[str, int] = {
    "AAA": 1, "AA+": 2, "AA": 3, "AA-": 4,
    "A+": 5, "A": 6, "A-": 7,
    "BBB+": 8, "BBB": 9, "BBB-": 10,
    "BB+": 11, "BB": 12, "BB-": 13,
    "B+": 14, "B": 15, "B-": 16,
    "CCC+": 17, "CCC": 18, "CCC-": 19,
    "CC": 20, "C": 21, "D": 22,
    # Moody's equivalents
    "Aaa": 1, "Aa1": 2, "Aa2": 3, "Aa3": 4,
    "A1": 5, "A2": 6, "A3": 7,
    "Baa1": 8, "Baa2": 9, "Baa3": 10,
    "Ba1": 11, "Ba2": 12, "Ba3": 13,
    "B1": 14, "B2": 15, "B3": 16,
    "Caa1": 17, "Caa2": 18, "Caa3": 19,
    "Ca": 20,
}


def _resolve_rating_numeric(bond: CorporateBond) -> int | None:
    """Derive a numeric rating from the bond's stored S&P, Moody's, or Fitch rating."""
    for rating_str in (bond.initial_rating_sp, bond.initial_rating_moodys, bond.initial_rating_fitch):
        if rating_str and rating_str in _RATING_MAP:
            return _RATING_MAP[rating_str]
    return None


@router.get(
    "/bonds/{cusip}/risk-metrics",
    response_model=BondRiskMetricsResponse,
)
async def get_bond_risk_metrics(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Full risk metrics for a single bond (DV01, rate/spread P&L, credit risk)."""
    bond = await _get_bond_by_cusip(cusip, session)

    # Get latest EOD price
    eod_query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(eod_query)
    eod = result.scalar_one_or_none()
    if eod is None:
        raise HTTPException(status_code=404, detail=f"No price data for bond {cusip}")

    trade_price = float(eod.last_trade_price) if eod.last_trade_price is not None else 100.0
    coupon_rate = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2
    face = 100.0

    # Compute years to maturity from price date
    days_to_mat = (bond.maturity_date - eod.price_date).days
    years_to_mat = max(days_to_mat / 365.25, 0.01)

    # Compute YTM
    ytm = compute_ytm(trade_price, coupon_rate, face, years_to_mat, freq)

    # Duration + convexity (bond_analytics functions take ytm, coupon_rate, years, freq)
    mod_dur = compute_modified_duration(ytm, coupon_rate, years_to_mat, freq)
    convexity = compute_convexity(ytm, coupon_rate, years_to_mat, freq)

    # Use modified duration as spread duration approximation
    spread_duration = mod_dur

    # Resolve rating
    rating_numeric = _resolve_rating_numeric(bond)
    seniority = bond.seniority or "SENIOR_UNSECURED"

    # Compute market value (assuming face = 100, so price IS the market value per 100 face)
    market_value = trade_price

    # Compute single bond risk
    risk = compute_single_bond_risk(
        market_value=market_value,
        modified_duration=mod_dur,
        convexity=convexity,
        spread_duration=spread_duration,
        rating_numeric=rating_numeric if rating_numeric is not None else 9,  # default BBB
        seniority=seniority,
    )

    return BondRiskMetricsResponse(
        cusip=cusip,
        dv01=risk["dv01"],
        rate_pnl_100bps=risk["rate_pnl_100bps"],
        spread_pnl_100bps=risk["spread_pnl_100bps"],
        expected_loss=risk["expected_loss"] if rating_numeric is not None else None,
        pd_1y=risk["pd_1y"] if rating_numeric is not None else None,
        lgd=risk["lgd"] if rating_numeric is not None else None,
        rating_numeric=rating_numeric,
    )
