"""Pillar 2 FI Supplement — Part 7: Issuer FI Profile API endpoints."""

import uuid
from datetime import date

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
from src.models.corporate_bond import CorporateBond
from src.models.entity import Entity
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

    # Simple refinancing risk assessment (without full E13 inputs)
    refi_result = compute_refinancing_risk(
        maturity_wall_pct=mat_2y_pct,
        current_spread_bps=200.0,  # default assumption
        fcf_to_debt=0.10,          # default assumption
        credit_direction=0.0,      # neutral
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
    current_spread_bps: float = Query(200.0, description="Current credit spread in bps"),
    fcf_to_debt: float = Query(0.10, description="FCF / total debt ratio"),
    credit_direction: float = Query(0.0, ge=-1.0, le=1.0, description="Credit direction (-1 to +1)"),
):
    """Get refinancing risk score for an issuer."""
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
