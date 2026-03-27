"""Competitive Intelligence API endpoints (Pillar 3 Phase 3A)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.competitive_intelligence import (
    CompetitiveLandscape,
    ConcentrationRiskAssessment,
    MoatAssessment,
    MoatHistory,
)
from src.schemas.competitive_intelligence import (
    CompetitiveLandscapeResponse,
    ConcentrationRiskResponse,
    MoatAssessmentResponse,
    MoatHistoryEntry,
    MoatHistoryResponse,
    PeerComparisonResponse,
)

router = APIRouter(tags=["Competitive Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── Moat endpoints ──────────────────────────────────────────────────


@router.get(
    "/competitive/{entity_id}/moat",
    response_model=MoatAssessmentResponse,
)
async def get_moat_assessment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest moat assessment for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(MoatAssessment)
        .where(MoatAssessment.entity_id == entity_id)
        .order_by(MoatAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No moat assessment found for this entity")

    return MoatAssessmentResponse(
        id=row.id,
        entity_id=row.entity_id,
        as_of_date=row.as_of_date,
        moat_width=row.moat_width,
        moat_stability=row.moat_stability,
        moat_score=float(row.moat_score) if row.moat_score is not None else None,
        roic_above_wacc_years=row.roic_above_wacc_years,
        roic_consistency_score=float(row.roic_consistency_score) if row.roic_consistency_score is not None else None,
        gross_margin_stability=float(row.gross_margin_stability) if row.gross_margin_stability is not None else None,
        gross_margin_10y_std=float(row.gross_margin_10y_std) if row.gross_margin_10y_std is not None else None,
        market_share_trend=row.market_share_trend,
        market_share_5y_delta=float(row.market_share_5y_delta) if row.market_share_5y_delta is not None else None,
        customer_retention_proxy=float(row.customer_retention_proxy) if row.customer_retention_proxy is not None else None,
        cost_advantage_score=float(row.cost_advantage_score) if row.cost_advantage_score is not None else None,
        network_effects_score=float(row.network_effects_score) if row.network_effects_score is not None else None,
        switching_costs_score=float(row.switching_costs_score) if row.switching_costs_score is not None else None,
        intangible_assets_score=float(row.intangible_assets_score) if row.intangible_assets_score is not None else None,
        efficient_scale_score=float(row.efficient_scale_score) if row.efficient_scale_score is not None else None,
        dominant_moat_source=row.dominant_moat_source,
        moat_evidence=row.moat_evidence,
        ai_summary=row.ai_summary,
        ai_enabled=row.ai_enabled,
    )


@router.get(
    "/competitive/{entity_id}/moat/evidence",
    response_model=dict,
)
async def get_moat_evidence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get moat evidence details for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(MoatAssessment)
        .where(MoatAssessment.entity_id == entity_id)
        .order_by(MoatAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No moat assessment found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "moat_width": row.moat_width,
        "dominant_moat_source": row.dominant_moat_source,
        "moat_evidence": row.moat_evidence or {},
        "cost_advantage_score": float(row.cost_advantage_score) if row.cost_advantage_score is not None else None,
        "network_effects_score": float(row.network_effects_score) if row.network_effects_score is not None else None,
        "switching_costs_score": float(row.switching_costs_score) if row.switching_costs_score is not None else None,
        "intangible_assets_score": float(row.intangible_assets_score) if row.intangible_assets_score is not None else None,
        "efficient_scale_score": float(row.efficient_scale_score) if row.efficient_scale_score is not None else None,
    }


@router.get(
    "/competitive/{entity_id}/moat/history",
    response_model=MoatHistoryResponse,
)
async def get_moat_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get historical moat metrics for trend analysis."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(MoatHistory)
        .where(MoatHistory.entity_id == entity_id)
        .order_by(MoatHistory.period_end_date.desc())
        .limit(20)
    )
    rows = result.scalars().all()

    history = [
        MoatHistoryEntry(
            id=row.id,
            entity_id=row.entity_id,
            period_end_date=row.period_end_date,
            moat_width=row.moat_width,
            moat_score=float(row.moat_score) if row.moat_score is not None else None,
            roic=float(row.roic) if row.roic is not None else None,
            wacc=float(row.wacc) if row.wacc is not None else None,
            roic_wacc_spread=float(row.roic_wacc_spread) if row.roic_wacc_spread is not None else None,
            gross_margin=float(row.gross_margin) if row.gross_margin is not None else None,
            market_share_est=float(row.market_share_est) if row.market_share_est is not None else None,
        )
        for row in rows
    ]

    return MoatHistoryResponse(entity_id=entity_id, history=history)


# ── Concentration endpoints ─────────────────────────────────────────


@router.get(
    "/competitive/{entity_id}/concentration",
    response_model=ConcentrationRiskResponse,
)
async def get_concentration_risk(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get overall concentration risk assessment."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ConcentrationRiskAssessment)
        .where(ConcentrationRiskAssessment.entity_id == entity_id)
        .order_by(ConcentrationRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No concentration risk assessment found for this entity")

    return ConcentrationRiskResponse(
        id=row.id,
        entity_id=row.entity_id,
        as_of_date=row.as_of_date,
        customer_top1_pct=float(row.customer_top1_pct) if row.customer_top1_pct is not None else None,
        customer_top5_pct=float(row.customer_top5_pct) if row.customer_top5_pct is not None else None,
        customer_top10_pct=float(row.customer_top10_pct) if row.customer_top10_pct is not None else None,
        customer_concentration_risk=row.customer_concentration_risk,
        customer_details=row.customer_details,
        supplier_single_source_count=row.supplier_single_source_count,
        supplier_critical_count=row.supplier_critical_count,
        supplier_geographic_concentration=row.supplier_geographic_concentration,
        supplier_concentration_risk=row.supplier_concentration_risk,
        supplier_details=row.supplier_details,
        geographic_revenue_breakdown=row.geographic_revenue_breakdown,
        geographic_top1_pct=float(row.geographic_top1_pct) if row.geographic_top1_pct is not None else None,
        geographic_hhi=float(row.geographic_hhi) if row.geographic_hhi is not None else None,
        fx_exposure_score=float(row.fx_exposure_score) if row.fx_exposure_score is not None else None,
        geographic_concentration_risk=row.geographic_concentration_risk,
        overall_concentration_risk=row.overall_concentration_risk,
        overall_risk_score=float(row.overall_risk_score) if row.overall_risk_score is not None else None,
    )


@router.get(
    "/competitive/{entity_id}/concentration/customers",
    response_model=dict,
)
async def get_customer_concentration(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get customer concentration detail."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ConcentrationRiskAssessment)
        .where(ConcentrationRiskAssessment.entity_id == entity_id)
        .order_by(ConcentrationRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No concentration risk assessment found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "customer_top1_pct": float(row.customer_top1_pct) if row.customer_top1_pct is not None else None,
        "customer_top5_pct": float(row.customer_top5_pct) if row.customer_top5_pct is not None else None,
        "customer_top10_pct": float(row.customer_top10_pct) if row.customer_top10_pct is not None else None,
        "customer_concentration_risk": row.customer_concentration_risk,
        "customer_details": row.customer_details or {},
    }


@router.get(
    "/competitive/{entity_id}/concentration/suppliers",
    response_model=dict,
)
async def get_supplier_concentration(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get supplier concentration detail."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ConcentrationRiskAssessment)
        .where(ConcentrationRiskAssessment.entity_id == entity_id)
        .order_by(ConcentrationRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No concentration risk assessment found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "supplier_single_source_count": row.supplier_single_source_count,
        "supplier_critical_count": row.supplier_critical_count,
        "supplier_geographic_concentration": row.supplier_geographic_concentration or {},
        "supplier_concentration_risk": row.supplier_concentration_risk,
        "supplier_details": row.supplier_details or {},
    }


@router.get(
    "/competitive/{entity_id}/concentration/geographic",
    response_model=dict,
)
async def get_geographic_concentration(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get geographic concentration detail."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ConcentrationRiskAssessment)
        .where(ConcentrationRiskAssessment.entity_id == entity_id)
        .order_by(ConcentrationRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No concentration risk assessment found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "geographic_revenue_breakdown": row.geographic_revenue_breakdown or {},
        "geographic_top1_pct": float(row.geographic_top1_pct) if row.geographic_top1_pct is not None else None,
        "geographic_hhi": float(row.geographic_hhi) if row.geographic_hhi is not None else None,
        "fx_exposure_score": float(row.fx_exposure_score) if row.fx_exposure_score is not None else None,
        "geographic_concentration_risk": row.geographic_concentration_risk,
    }


# ── Landscape endpoints ─────────────────────────────────────────────


@router.get(
    "/competitive/{entity_id}/landscape",
    response_model=CompetitiveLandscapeResponse,
)
async def get_competitive_landscape(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get competitive landscape for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompetitiveLandscape)
        .where(CompetitiveLandscape.entity_id == entity_id)
        .order_by(CompetitiveLandscape.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No competitive landscape found for this entity")

    return CompetitiveLandscapeResponse(
        id=row.id,
        entity_id=row.entity_id,
        gics_code=row.gics_code,
        as_of_date=row.as_of_date,
        peer_group=row.peer_group,
        market_share_est_pct=float(row.market_share_est_pct) if row.market_share_est_pct is not None else None,
        market_share_rank=row.market_share_rank,
        revenue_growth_vs_peers=float(row.revenue_growth_vs_peers) if row.revenue_growth_vs_peers is not None else None,
        margin_vs_peers=float(row.margin_vs_peers) if row.margin_vs_peers is not None else None,
        roic_vs_peers=float(row.roic_vs_peers) if row.roic_vs_peers is not None else None,
        valuation_vs_peers=row.valuation_vs_peers,
        share_gainer=row.share_gainer,
        value_chain_position=row.value_chain_position,
        competitive_advantages=row.competitive_advantages,
        competitive_threats=row.competitive_threats,
    )


@router.get(
    "/competitive/{entity_id}/peers",
    response_model=list[PeerComparisonResponse],
)
async def get_peers(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get peer comparison entries for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompetitiveLandscape)
        .where(CompetitiveLandscape.entity_id == entity_id)
        .order_by(CompetitiveLandscape.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return []

    # Extract peers from the peer_group JSONB
    peers = []
    if row.peer_group and isinstance(row.peer_group, list):
        for peer in row.peer_group:
            peers.append(
                PeerComparisonResponse(
                    entity_id=peer.get("entity_id", entity_id),
                    entity_name=peer.get("entity_name"),
                    market_share_est_pct=peer.get("market_share_est_pct"),
                    market_share_rank=peer.get("market_share_rank"),
                    revenue_growth_vs_peers=peer.get("revenue_growth_vs_peers"),
                    margin_vs_peers=peer.get("margin_vs_peers"),
                    roic_vs_peers=peer.get("roic_vs_peers"),
                )
            )

    return peers


@router.get(
    "/competitive/{entity_id}/market-share",
    response_model=dict,
)
async def get_market_share(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get market share data for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompetitiveLandscape)
        .where(CompetitiveLandscape.entity_id == entity_id)
        .order_by(CompetitiveLandscape.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No competitive landscape found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "market_share_est_pct": float(row.market_share_est_pct) if row.market_share_est_pct is not None else None,
        "market_share_rank": row.market_share_rank,
        "share_gainer": row.share_gainer,
    }


@router.get(
    "/competitive/{entity_id}/relationships",
    response_model=dict,
)
async def get_competitive_relationships(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get competitive relationship data (advantages/threats)."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompetitiveLandscape)
        .where(CompetitiveLandscape.entity_id == entity_id)
        .order_by(CompetitiveLandscape.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No competitive landscape found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "competitive_advantages": row.competitive_advantages or {},
        "competitive_threats": row.competitive_threats or {},
    }


@router.get(
    "/competitive/{entity_id}/value-chain",
    response_model=dict,
)
async def get_value_chain(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get value chain position for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompetitiveLandscape)
        .where(CompetitiveLandscape.entity_id == entity_id)
        .order_by(CompetitiveLandscape.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No competitive landscape found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "gics_code": row.gics_code,
        "value_chain_position": row.value_chain_position,
        "peer_group": row.peer_group or {},
    }
