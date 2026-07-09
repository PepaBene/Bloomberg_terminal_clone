"""Pillar 2 FI Supplement – Part 4: Credit Quality Analytics API endpoints."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e13_credit_quality import (
    compute_credit_momentum,
    compute_fallen_angel_probability,
    compute_ohlson_o_score,
    compute_refinancing_risk,
)
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod
from src.schemas.fi_credit_quality import (
    CreditMomentumComponents,
    CreditMomentumResponse,
    CreditQualityResponse,
    FallenAngelWatchItem,
    FallenAngelWatchResponse,
    RefinancingRiskComponents,
    RefinancingRiskResponse,
)

router = APIRouter(prefix="/v2/analytics", tags=["Credit Quality Analytics"])


# ── Real-data helpers for momentum / O-Score ────────────────────────


def _to_float(value) -> float | None:
    return float(value) if value is not None else None


async def _rating_change_signal(
    session: AsyncSession, entity_id: uuid.UUID, lookback_days: int = 730
) -> float | None:
    """Net rating change over the lookback window, normalized to [-1, +1].

    Positive = net upgrades (numeric rating decreased). Returns None when no
    rating events exist. Saturates at +/-1 for >= 3 notches of net change.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    query = select(CreditRatingEvent).where(
        CreditRatingEvent.entity_id == entity_id,
        CreditRatingEvent.event_date >= cutoff,
    )
    events = (await session.execute(query)).scalars().all()
    if not events:
        return None

    net_notches = 0.0
    for e in events:
        if e.new_rating_numeric is not None and e.old_rating_numeric is not None:
            # Lower numeric = better rating, so old - new > 0 means an upgrade.
            net_notches += e.old_rating_numeric - e.new_rating_numeric
        elif e.notches_changed is not None and e.direction:
            mag = abs(e.notches_changed)
            direction = e.direction.upper()
            if direction in ("UPGRADE", "POSITIVE", "RAISED"):
                net_notches += mag
            elif direction in ("DOWNGRADE", "NEGATIVE", "LOWERED"):
                net_notches -= mag

    return max(-1.0, min(1.0, net_notches / 3.0))


async def _spread_momentum(
    session: AsyncSession, bond_id: uuid.UUID, lookback_days: int = 180
) -> float | None:
    """Spread trend for a bond over the lookback, normalized to [-1, +1].

    Positive = tightening (improving credit); negative = widening. Returns None
    when fewer than two G-spread observations exist in the window.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    query = (
        select(BondEODPrice)
        .where(
            BondEODPrice.bond_id == bond_id,
            BondEODPrice.g_spread_bps.isnot(None),
            BondEODPrice.price_date >= cutoff,
        )
        .order_by(BondEODPrice.price_date.asc())
    )
    rows = (await session.execute(query)).scalars().all()
    if len(rows) < 2:
        return None

    earliest = float(rows[0].g_spread_bps)
    latest = float(rows[-1].g_spread_bps)
    if earliest <= 0:
        return None
    # Tightening (spread fell) is an improvement -> positive momentum.
    return max(-1.0, min(1.0, (earliest - latest) / earliest))


async def _load_annual_periods(
    session: AsyncSession, entity_id: uuid.UUID, limit: int = 3
) -> list[FinancialPeriod]:
    """Load the most recent ANNUAL periods that carry income + balance sheets."""
    query = (
        select(FinancialPeriod)
        .where(
            FinancialPeriod.entity_id == entity_id,
            FinancialPeriod.period_type == "ANNUAL",
        )
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(limit)
    )
    periods = list((await session.execute(query)).scalars().all())
    return [
        p
        for p in periods
        if p.income_statement is not None and p.balance_sheet is not None
    ]


def _compute_o_score_for_period(
    period: FinancialPeriod, prior_period: FinancialPeriod | None
) -> dict | None:
    """Compute the Ohlson O-Score for a period from its real financial statements."""
    bs = period.balance_sheet
    inc = period.income_statement
    cf = period.cash_flow
    if bs is None or inc is None:
        return None

    total_assets = _to_float(bs.total_assets)
    if not total_assets:
        return None

    working_capital = _to_float(bs.working_capital)
    if working_capital is None:
        tca = _to_float(bs.total_current_assets)
        tcl = _to_float(bs.total_current_liabilities)
        working_capital = (tca - tcl) if (tca is not None and tcl is not None) else 0.0

    net_income = _to_float(inc.net_income) or 0.0
    ffo = _to_float(cf.cash_from_operations) if cf is not None else None
    if ffo is None:
        ffo = net_income  # proxy when the cash-flow statement is unavailable

    ni_lag = 0.0
    ta_lag = total_assets
    consecutive_loss = 0
    if prior_period is not None and prior_period.income_statement is not None:
        ni_lag = _to_float(prior_period.income_statement.net_income) or 0.0
        if prior_period.balance_sheet is not None:
            ta_lag = _to_float(prior_period.balance_sheet.total_assets) or total_assets
        if net_income < 0 and ni_lag < 0:
            consecutive_loss = 2

    return compute_ohlson_o_score(
        total_assets=total_assets,
        total_liabilities=_to_float(bs.total_liabilities) or 0.0,
        working_capital=working_capital,
        current_liabilities=_to_float(bs.total_current_liabilities) or 0.0,
        net_income=net_income,
        funds_from_operations=ffo,
        total_debt=_to_float(bs.total_debt) or 0.0,
        net_income_lag1=ni_lag,
        total_assets_lag1=ta_lag,
        consecutive_loss_years=consecutive_loss,
    )


# ── 1. GET /bonds/{cusip}/credit ───────────────────────────────────


@router.get(
    "/bonds/{cusip}/credit",
    response_model=CreditQualityResponse,
)
async def get_bond_credit_quality(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Compute credit quality metrics for a bond: O-Score, momentum, fallen angel, refi risk.

    Looks up the bond by CUSIP, finds the issuer entity, retrieves the
    current credit rating, and computes all available credit quality metrics.
    """
    # 1. Look up bond
    bond_result = await session.execute(
        select(CorporateBond).where(CorporateBond.cusip == cusip)
    )
    bond = bond_result.scalar_one_or_none()
    if bond is None:
        raise HTTPException(status_code=404, detail=f"Bond with CUSIP {cusip} not found")

    entity_id = bond.issuer_entity_id

    # 2. Retrieve current credit rating for the issuer
    rating_result = await session.execute(
        select(CurrentCreditRating).where(
            CurrentCreditRating.entity_id == entity_id
        )
    )
    ratings = rating_result.scalars().all()

    # Use the first available rating (prefer SP)
    current_rating = None
    for r in sorted(ratings, key=lambda x: (x.agency != "SP", x.agency)):
        current_rating = r
        break

    # 3. Compute fallen angel probability
    fallen_angel_prob = None
    if current_rating and current_rating.current_rating_numeric is not None:
        fallen_angel_prob = compute_fallen_angel_probability(
            current_rating_numeric=current_rating.current_rating_numeric,
            outlook=current_rating.outlook,
            watch_status=current_rating.watch_status,
        )

    # 4. Compute the Ohlson O-Score from the issuer's real annual financials.
    #    score_momentum is derived from the change in default probability
    #    between the two most recent annual periods.
    periods = await _load_annual_periods(session, entity_id)
    o_score_val: float | None = None
    pod_val: float | None = None
    score_momentum = 0.0
    fcf_to_debt: float | None = None
    if periods:
        latest_p = periods[0]
        prior_p = periods[1] if len(periods) > 1 else None
        o_res = _compute_o_score_for_period(latest_p, prior_p)
        if o_res is not None:
            o_score_val = o_res["o_score"]
            pod_val = o_res["probability_of_default"]
            if prior_p is not None:
                prior_res = _compute_o_score_for_period(
                    prior_p, periods[2] if len(periods) > 2 else None
                )
                if prior_res is not None:
                    # Falling default probability = improving credit = positive.
                    score_momentum = max(
                        -1.0,
                        min(
                            1.0,
                            (prior_res["probability_of_default"] - pod_val) * 10.0,
                        ),
                    )
        # Real FCF/debt for the refinancing-risk computation below.
        bs = latest_p.balance_sheet
        cf = latest_p.cash_flow
        total_debt = _to_float(bs.total_debt) if bs is not None else None
        fcf = _to_float(cf.free_cash_flow) if cf is not None else None
        if total_debt and total_debt > 0 and fcf is not None:
            fcf_to_debt = fcf / total_debt

    # 5. Credit momentum from real rating changes, O-Score trend and spread trend.
    rating_signal = await _rating_change_signal(session, entity_id)
    rating_momentum = rating_signal if rating_signal is not None else 0.0
    spread_signal = await _spread_momentum(session, bond.bond_id)
    spread_momentum = spread_signal if spread_signal is not None else 0.0

    momentum_result = compute_credit_momentum(
        rating_momentum=rating_momentum,
        score_momentum=score_momentum,
        spread_momentum=spread_momentum,
    )

    # 6. Compute refinancing risk with available data.
    # Get latest spread from EOD prices if available
    eod_result = await session.execute(
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    eod = eod_result.scalar_one_or_none()
    spread_bps = float(eod.g_spread_bps) if eod and eod.g_spread_bps else 200.0

    refi_result = compute_refinancing_risk(
        # maturity_wall_pct: full debt-schedule concentration is computed by the
        # issuer-profile endpoint (which sees all of the issuer's bonds); here we
        # use a neutral estimate since this route is scoped to a single bond.
        maturity_wall_pct=30.0,
        current_spread_bps=spread_bps,
        fcf_to_debt=fcf_to_debt if fcf_to_debt is not None else 0.15,
        credit_direction=rating_momentum,  # real rating-change direction
    )

    return CreditQualityResponse(
        cusip=cusip,
        o_score=o_score_val,
        probability_of_default=pod_val,
        credit_momentum_score=momentum_result["momentum_score"],
        credit_momentum_signal=momentum_result["signal"],
        fallen_angel_probability=fallen_angel_prob,
        refinancing_risk_score=refi_result["score"] if refi_result else None,
        refinancing_risk_assessment=refi_result["assessment"] if refi_result else None,
    )


# ── 2. GET /entities/{entity_id}/credit-momentum ──────────────────


@router.get(
    "/entities/{entity_id}/credit-momentum",
    response_model=CreditMomentumResponse,
)
async def get_credit_momentum(
    entity_id: uuid.UUID,
    rating_momentum: float = Query(0.0, ge=-1.0, le=1.0, description="Rating momentum (-1 to +1)"),
    score_momentum: float = Query(0.0, ge=-1.0, le=1.0, description="Score momentum (-1 to +1)"),
    spread_momentum: float = Query(0.0, ge=-1.0, le=1.0, description="Spread momentum (-1 to +1)"),
    session: AsyncSession = Depends(get_session),
):
    """Compute credit momentum for an entity.

    Accepts rating_momentum, score_momentum, spread_momentum as query params
    (each ranging from -1 to +1). Returns weighted momentum score and signal.
    """
    # Verify entity exists
    entity_result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = entity_result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    result = compute_credit_momentum(
        rating_momentum=rating_momentum,
        score_momentum=score_momentum,
        spread_momentum=spread_momentum,
    )

    return CreditMomentumResponse(
        entity_id=str(entity_id),
        momentum_score=result["momentum_score"],
        signal=result["signal"],
        components=CreditMomentumComponents(**result["components"]),
    )


# ── 3. GET /entities/fallen-angel-watch ────────────────────────────


@router.get(
    "/entities/fallen-angel-watch",
    response_model=FallenAngelWatchResponse,
)
async def get_fallen_angel_watch(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
):
    """List BBB-rated entities ranked by fallen angel (downgrade to HY) probability.

    Queries CurrentCreditRating for entities with rating_numeric 8-10
    (BBB+/BBB/BBB-) and computes the fallen angel probability for each.
    """
    # Find all BBB-rated entities (numeric 8, 9, 10)
    rating_query = select(CurrentCreditRating).where(
        CurrentCreditRating.current_rating_numeric.in_([8, 9, 10])
    )
    rating_result = await session.execute(rating_query)
    bbb_ratings = rating_result.scalars().all()

    if not bbb_ratings:
        return FallenAngelWatchResponse(entities=[], total=0)

    # Collect unique entity IDs and fetch entity names
    entity_ids = list({r.entity_id for r in bbb_ratings})
    entity_query = select(Entity).where(Entity.entity_id.in_(entity_ids))
    entity_result = await session.execute(entity_query)
    entities = {e.entity_id: e for e in entity_result.scalars().all()}

    # Compute fallen angel probability for each
    watch_items: list[FallenAngelWatchItem] = []
    for rating in bbb_ratings:
        prob = compute_fallen_angel_probability(
            current_rating_numeric=rating.current_rating_numeric,
            outlook=rating.outlook,
            watch_status=rating.watch_status,
        )
        entity = entities.get(rating.entity_id)
        watch_items.append(
            FallenAngelWatchItem(
                entity_id=str(rating.entity_id),
                entity_name=entity.legal_name if entity else None,
                current_rating=rating.current_rating,
                current_rating_numeric=rating.current_rating_numeric,
                outlook=rating.outlook,
                watch_status=rating.watch_status,
                fallen_angel_probability=prob,
            )
        )

    # Sort by probability descending
    watch_items.sort(key=lambda x: x.fallen_angel_probability, reverse=True)
    watch_items = watch_items[:limit]

    return FallenAngelWatchResponse(
        entities=watch_items,
        total=len(watch_items),
    )


# ── 4. GET /entities/{entity_id}/refinancing-risk ──────────────────


@router.get(
    "/entities/{entity_id}/refinancing-risk",
    response_model=RefinancingRiskResponse,
)
async def get_refinancing_risk(
    entity_id: uuid.UUID,
    maturity_wall_pct: float = Query(30.0, ge=0, le=100, description="% of debt maturing in next 2 years"),
    current_spread_bps: float = Query(200.0, ge=0, description="Current credit spread in bps"),
    fcf_to_debt: float = Query(0.15, ge=0, description="FCF / total debt ratio"),
    credit_direction: float = Query(0.0, ge=-1.0, le=1.0, description="Credit direction (-1 to +1)"),
    session: AsyncSession = Depends(get_session),
):
    """Compute refinancing risk score for an entity.

    Accepts maturity_wall_pct, current_spread_bps, fcf_to_debt, credit_direction
    as query params. Returns weighted risk score and assessment.
    """
    # Verify entity exists
    entity_result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = entity_result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    result = compute_refinancing_risk(
        maturity_wall_pct=maturity_wall_pct,
        current_spread_bps=current_spread_bps,
        fcf_to_debt=fcf_to_debt,
        credit_direction=credit_direction,
    )

    return RefinancingRiskResponse(
        entity_id=str(entity_id),
        score=result["score"],
        assessment=result["assessment"],
        components=RefinancingRiskComponents(**result["components"]),
        maturity_wall_pct=maturity_wall_pct,
        current_spread_bps=current_spread_bps,
    )
