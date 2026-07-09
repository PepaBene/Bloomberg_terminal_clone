"""Pillar 2 FI Supplement — Part 7: Issuer FI Profile API endpoints."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e13_credit_quality import compute_refinancing_risk
from src.engines.e14_issuer_profile import (
    build_debt_stack,
    compute_debt_maturity_profile,
    compute_maturity_wall,
    compute_weighted_avg_cost_of_debt,
)
from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.credit_rating import CreditRatingEvent
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod
from src.schemas.fi_issuer_profile import (
    DebtStackItem,
    DebtStackResponse,
    IssuerFIProfileResponse,
    MaturityWallItem,
    MaturityWallResponse,
    RefinancingRiskResponse,
)

router = APIRouter(prefix="/v2/analytics", tags=["FI Issuer Profile"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    """Fetch an Entity by ID or raise 404."""
    query = select(Entity).where(Entity.entity_id == entity_id)
    result = await session.execute(query)
    entity = result.scalars().unique().one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return entity


async def _get_bonds_for_entity(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[CorporateBond]:
    """Get all outstanding corporate bonds for an entity."""
    query = (
        select(CorporateBond)
        .where(CorporateBond.issuer_entity_id == entity_id)
        .where(CorporateBond.status == "OUTSTANDING")
    )
    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def _entity_current_spread_bps(
    session: AsyncSession, bonds: list[CorporateBond]
) -> float | None:
    """Average of each bond's most recent G-spread across the issuer's bonds."""
    spreads: list[float] = []
    for bond in bonds:
        query = (
            select(BondEODPrice.g_spread_bps)
            .where(
                BondEODPrice.bond_id == bond.bond_id,
                BondEODPrice.g_spread_bps.isnot(None),
            )
            .order_by(BondEODPrice.price_date.desc())
            .limit(1)
        )
        latest = (await session.execute(query)).scalar_one_or_none()
        if latest is not None:
            spreads.append(float(latest))
    if not spreads:
        return None
    return sum(spreads) / len(spreads)


async def _entity_fcf_to_debt(
    session: AsyncSession, entity_id: uuid.UUID
) -> float | None:
    """FCF / total debt from the issuer's latest ANNUAL financial period."""
    query = (
        select(FinancialPeriod)
        .where(
            FinancialPeriod.entity_id == entity_id,
            FinancialPeriod.period_type == "ANNUAL",
        )
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(4)
    )
    periods = (await session.execute(query)).scalars().all()
    for period in periods:
        bs = period.balance_sheet
        cf = period.cash_flow
        if bs is None or cf is None:
            continue
        total_debt = float(bs.total_debt) if bs.total_debt is not None else None
        fcf = float(cf.free_cash_flow) if cf.free_cash_flow is not None else None
        if total_debt and total_debt > 0 and fcf is not None:
            return fcf / total_debt
    return None


async def _entity_credit_direction(
    session: AsyncSession, entity_id: uuid.UUID, lookback_days: int = 730
) -> float | None:
    """Net rating change over the lookback, normalized to [-1, +1].

    Positive = net upgrades (improving); saturates at +/-1 for >= 3 notches.
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
            net_notches += e.old_rating_numeric - e.new_rating_numeric
        elif e.notches_changed is not None and e.direction:
            mag = abs(e.notches_changed)
            direction = e.direction.upper()
            if direction in ("UPGRADE", "POSITIVE", "RAISED"):
                net_notches += mag
            elif direction in ("DOWNGRADE", "NEGATIVE", "LOWERED"):
                net_notches -= mag

    return max(-1.0, min(1.0, net_notches / 3.0))


def _bond_to_dict(bond: CorporateBond) -> dict:
    """Convert a CorporateBond ORM object to a dict for the engine."""
    return {
        "cusip": bond.cusip,
        "maturity_date": bond.maturity_date,
        "outstanding_amount": float(bond.outstanding_amount) if bond.outstanding_amount else 0.0,
        "coupon_rate": float(bond.coupon_rate) if bond.coupon_rate else 0.0,
        "seniority": bond.seniority or "SENIOR_UNSECURED",
    }


# ── 1. GET /entities/{entity_id}/fi-profile ──────────────────────────


@router.get(
    "/entities/{entity_id}/fi-profile",
    response_model=IssuerFIProfileResponse,
)
async def get_issuer_fi_profile(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    years_forward: int = Query(5, ge=1, le=30, description="Maturity wall window in years"),
):
    """Get complete FI profile for an issuer: debt stack, maturity wall, weighted cost."""
    entity = await _get_entity(session, entity_id)
    bonds = await _get_bonds_for_entity(session, entity_id)

    if not bonds:
        raise HTTPException(
            status_code=404,
            detail=f"No outstanding bonds found for entity {entity_id}",
        )

    bond_dicts = [_bond_to_dict(b) for b in bonds]

    # Compute components
    maturity_wall = compute_maturity_wall(bond_dicts, years_forward=years_forward)
    debt_stack = build_debt_stack(bond_dicts)
    weighted_coupon = compute_weighted_avg_cost_of_debt(bond_dicts)
    maturity_profile = compute_debt_maturity_profile(bond_dicts)

    # Refinancing risk: % maturing in next 2 years
    today = date.today()
    two_year_wall = compute_maturity_wall(bond_dicts, reference_date=today, years_forward=2)
    total_outstanding = maturity_profile["total_outstanding"]
    mat_2y_amount = sum(item["amount_maturing"] for item in two_year_wall)
    mat_2y_pct = (mat_2y_amount / total_outstanding * 100.0) if total_outstanding > 0 else 0.0

    # Refinancing-risk inputs derived from the issuer's real data. Maturity-wall
    # concentration is fully real; spread, leverage (FCF/debt) and credit
    # direction are pulled from real tables and only fall back to conservative
    # constants when no source row exists for this issuer.
    real_spread = await _entity_current_spread_bps(session, bonds)
    real_fcf_to_debt = await _entity_fcf_to_debt(session, entity_id)
    real_direction = await _entity_credit_direction(session, entity_id)
    refi_result = compute_refinancing_risk(
        maturity_wall_pct=mat_2y_pct,
        current_spread_bps=real_spread if real_spread is not None else 200.0,
        fcf_to_debt=real_fcf_to_debt if real_fcf_to_debt is not None else 0.10,
        credit_direction=real_direction if real_direction is not None else 0.0,
    )

    return IssuerFIProfileResponse(
        entity_id=str(entity_id),
        entity_name=entity.legal_name,
        total_debt_outstanding=total_outstanding,
        bond_count=len(bonds),
        weighted_avg_coupon=round(weighted_coupon, 6),
        weighted_avg_maturity_years=maturity_profile["weighted_avg_maturity_years"],
        maturity_wall=[
            MaturityWallItem(
                year=item["year"],
                amount_maturing=item["amount_maturing"],
                pct_of_total=item["pct_of_total"],
                bond_count=item["bond_count"],
            )
            for item in maturity_wall
        ],
        debt_stack=[
            DebtStackItem(**item) for item in debt_stack
        ],
        refinancing_risk_score=refi_result["score"],
        refinancing_risk_assessment=refi_result["assessment"],
    )


# ── 2. GET /entities/{entity_id}/fi-profile/maturity-wall ────────────


@router.get(
    "/entities/{entity_id}/fi-profile/maturity-wall",
    response_model=MaturityWallResponse,
)
async def get_maturity_wall(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    years_forward: int = Query(5, ge=1, le=30, description="Years to look forward"),
):
    """Get maturity wall for an issuer — debt maturing by year."""
    await _get_entity(session, entity_id)
    bonds = await _get_bonds_for_entity(session, entity_id)

    if not bonds:
        raise HTTPException(
            status_code=404,
            detail=f"No outstanding bonds found for entity {entity_id}",
        )

    bond_dicts = [_bond_to_dict(b) for b in bonds]
    total_outstanding = sum(d["outstanding_amount"] for d in bond_dicts)
    maturity_wall = compute_maturity_wall(bond_dicts, years_forward=years_forward)

    return MaturityWallResponse(
        entity_id=str(entity_id),
        maturity_wall=[
            MaturityWallItem(
                year=item["year"],
                amount_maturing=item["amount_maturing"],
                pct_of_total=item["pct_of_total"],
                bond_count=item["bond_count"],
            )
            for item in maturity_wall
        ],
        total_outstanding=total_outstanding,
        years_forward=years_forward,
    )


# ── 3. GET /entities/{entity_id}/fi-profile/debt-stack ───────────────


@router.get(
    "/entities/{entity_id}/fi-profile/debt-stack",
    response_model=DebtStackResponse,
)
async def get_debt_stack(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get debt stack for an issuer — debt grouped by seniority."""
    await _get_entity(session, entity_id)
    bonds = await _get_bonds_for_entity(session, entity_id)

    if not bonds:
        raise HTTPException(
            status_code=404,
            detail=f"No outstanding bonds found for entity {entity_id}",
        )

    bond_dicts = [_bond_to_dict(b) for b in bonds]
    total_outstanding = sum(d["outstanding_amount"] for d in bond_dicts)
    debt_stack = build_debt_stack(bond_dicts)

    return DebtStackResponse(
        entity_id=str(entity_id),
        debt_stack=[DebtStackItem(**item) for item in debt_stack],
        total_outstanding=total_outstanding,
    )


# ── 4. GET /entities/{entity_id}/fi-profile/refinancing-risk ─────────


@router.get(
    "/entities/{entity_id}/fi-profile/refinancing-risk",
    response_model=RefinancingRiskResponse,
)
async def get_refinancing_risk(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_spread_bps: float | None = Query(
        None, description="Override credit spread in bps (defaults to issuer's real latest spread)"
    ),
    fcf_to_debt: float | None = Query(
        None, description="Override FCF / total debt ratio (defaults to issuer's real ratio)"
    ),
    credit_direction: float | None = Query(
        None, ge=-1.0, le=1.0, description="Override credit direction (defaults to real rating trend)"
    ),
):
    """Get refinancing risk score for an issuer.

    All four inputs are derived from the issuer's real data by default:
    maturity-wall concentration from the debt schedule, credit spread from bond
    EOD prices, FCF/debt from the latest annual financials, and credit direction
    from recent rating actions. Query params override any of these.
    """
    await _get_entity(session, entity_id)
    bonds = await _get_bonds_for_entity(session, entity_id)

    if not bonds:
        raise HTTPException(
            status_code=404,
            detail=f"No outstanding bonds found for entity {entity_id}",
        )

    bond_dicts = [_bond_to_dict(b) for b in bonds]
    total_outstanding = sum(d["outstanding_amount"] for d in bond_dicts)

    # % maturing in next 2 years
    today = date.today()
    two_year_wall = compute_maturity_wall(bond_dicts, reference_date=today, years_forward=2)
    mat_2y_amount = sum(item["amount_maturing"] for item in two_year_wall)
    mat_2y_pct = (mat_2y_amount / total_outstanding * 100.0) if total_outstanding > 0 else 0.0

    # Resolve each input: caller override -> real data -> conservative fallback.
    if current_spread_bps is None:
        real_spread = await _entity_current_spread_bps(session, bonds)
        current_spread_bps = real_spread if real_spread is not None else 200.0
    if fcf_to_debt is None:
        real_fcf_to_debt = await _entity_fcf_to_debt(session, entity_id)
        fcf_to_debt = real_fcf_to_debt if real_fcf_to_debt is not None else 0.10
    if credit_direction is None:
        real_direction = await _entity_credit_direction(session, entity_id)
        credit_direction = real_direction if real_direction is not None else 0.0

    result = compute_refinancing_risk(
        maturity_wall_pct=mat_2y_pct,
        current_spread_bps=current_spread_bps,
        fcf_to_debt=fcf_to_debt,
        credit_direction=credit_direction,
    )

    return RefinancingRiskResponse(
        entity_id=str(entity_id),
        score=result["score"],
        assessment=result["assessment"],
        maturity_wall_pct_2y=round(mat_2y_pct, 2),
        current_spread_bps=current_spread_bps,
    )
