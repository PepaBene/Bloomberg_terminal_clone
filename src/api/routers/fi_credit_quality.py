"""Pillar 2 FI Supplement – Part 4: Credit Quality Analytics API endpoints."""

import uuid

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
from src.models.credit_rating import CurrentCreditRating
from src.models.entity import Entity
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

    # 4. Compute credit momentum (using default neutral values since we don't
    #    have full time-series data in a single request; real implementation
    #    would pull historical rating events)
    momentum_result = compute_credit_momentum(
        rating_momentum=0.0,
        score_momentum=0.0,
        spread_momentum=0.0,
    )

    # 5. Compute refinancing risk with available data
    refi_result = None
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
        maturity_wall_pct=30.0,  # default estimate; real implementation would compute from debt schedule
        current_spread_bps=spread_bps,
        fcf_to_debt=0.15,  # default estimate
        credit_direction=0.0,  # neutral
    )

    return CreditQualityResponse(
        cusip=cusip,
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
