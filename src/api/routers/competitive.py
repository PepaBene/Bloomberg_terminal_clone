"""Competitive Intelligence API endpoints (Pillar 3 Phase 3A)."""

import uuid
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import competitive_landscape as cl_engine
from src.engines import concentration_risk as cr_engine
from src.engines import moat_assessment as moat_engine
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod, IncomeStatement, SegmentData
from src.models.relationships import BusinessRelationship
from src.models.competitive_intelligence import (
    CompetitiveLandscape,
    ConcentrationRiskAssessment,
    MoatAssessment,
    MoatHistory,
)
from src.models.industry_intelligence import IndustryCompetitiveStructure, IndustryProfile
from src.schemas.competitive_intelligence import (
    CompetitiveLandscapeResponse,
    ConcentrationRiskResponse,
    MoatAssessmentResponse,
    MoatHistoryEntry,
    MoatHistoryResponse,
    PeerComparisonResponse,
)

router = APIRouter(tags=["Competitive Intelligence"])


async def _entity_metrics(session: AsyncSession, entity_id: uuid.UUID) -> dict | None:
    """Compact per-entity metric bundle used across the competitive engines."""
    periods = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .order_by(FinancialPeriod.period_end_date.asc())
            .limit(8)
        )
    ).scalars().all()
    if not periods:
        return None
    latest = periods[-1]
    inc = latest.income_statement
    if not inc or inc.total_revenue is None or float(inc.total_revenue) <= 0:
        return None
    rev = float(inc.total_revenue)

    gm_hist = []
    for p in periods:
        pi = p.income_statement
        if pi and pi.total_revenue and pi.gross_profit is not None:
            gm_hist.append(round(float(pi.gross_profit) / float(pi.total_revenue) * 100, 2))

    revenue_growth = None
    if len(periods) > 1 and periods[-2].income_statement and periods[-2].income_statement.total_revenue:
        prev = float(periods[-2].income_statement.total_revenue)
        if prev:
            revenue_growth = round((rev - prev) / prev * 100, 2)

    operating_margin = round(float(inc.operating_income) / rev * 100, 2) if inc.operating_income is not None else None
    capex_intensity = 0.0
    if latest.cash_flow and latest.cash_flow.capital_expenditures is not None:
        capex_intensity = round(abs(float(latest.cash_flow.capital_expenditures)) / rev * 100, 2)

    met = {}
    for name, val in (
        await session.execute(
            select(AnalyticsResult.metric_name, AnalyticsResult.value)
            .where(AnalyticsResult.entity_id == entity_id,
                   AnalyticsResult.metric_name.in_(["roic", "wacc"]))
            .order_by(AnalyticsResult.as_of_date.desc())
        )
    ).all():
        if val is not None and name not in met:
            met[name] = float(val)

    return {
        "revenue": rev,
        "revenue_growth": revenue_growth,
        "operating_margin": operating_margin,
        "gross_margin_history": gm_hist,
        "capex_intensity": capex_intensity,
        "roic": met.get("roic"),
        "wacc": met.get("wacc"),
    }


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _finest_gics(entity: Entity) -> str | None:
    for attr in ("gics_sub_industry", "gics_industry", "gics_industry_group", "gics_sector"):
        val = getattr(entity, attr, None)
        if val:
            return val
    return None


async def _upsert_competitive(session, model, entity_id, as_of, values: dict, extra_key=None) -> None:
    where = [model.entity_id == entity_id, model.as_of_date == as_of]
    existing = (await session.execute(select(model).where(*where))).scalar_one_or_none()
    if existing is not None:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(model(id=uuid.uuid4(), entity_id=entity_id, as_of_date=as_of, **values))


async def _compute_competitive(session: AsyncSession, entity: Entity) -> bool:
    """Compute + persist moat / competitive landscape / concentration risk for
    an entity from real Pillar 1/2 data, sourcing industry/peer aggregates from
    the industry-intelligence producer. Returns False when there's not enough
    data (no fundamentals). The three engines had no production caller before."""
    entity_id = entity.entity_id
    me = await _entity_metrics(session, entity_id)
    if me is None:
        return False

    today = date.today()
    gics_code = _finest_gics(entity)

    # ── Industry / peer aggregates ────────────────────────────────────
    profile = structure = None
    peers: list[dict] = []
    if gics_code:
        from src.api.routers.industry import _compute_industry_intelligence, _gics_filter

        profile = (await session.execute(
            select(IndustryProfile).where(IndustryProfile.gics_code == gics_code)
            .order_by(IndustryProfile.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
        if profile is None:
            await _compute_industry_intelligence(session, gics_code)
            profile = (await session.execute(
                select(IndustryProfile).where(IndustryProfile.gics_code == gics_code)
                .order_by(IndustryProfile.as_of_date.desc()).limit(1)
            )).scalar_one_or_none()
        structure = (await session.execute(
            select(IndustryCompetitiveStructure).where(IndustryCompetitiveStructure.gics_code == gics_code)
            .order_by(IndustryCompetitiveStructure.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()

        peer_ids = (await session.execute(
            select(Entity.entity_id, Entity.legal_name)
            .where(_gics_filter(gics_code), Entity.status != "INACTIVE").limit(60)
        )).all()
        for pid, pname in peer_ids:
            pm = await _entity_metrics(session, pid)
            if pm is None:
                continue
            peers.append({
                "entity_id": str(pid), "name": pname, "revenue": pm["revenue"],
                "revenue_growth": pm["revenue_growth"], "operating_margin": pm["operating_margin"],
                "roic": pm["roic"], "market_cap": None,
            })

    total_rev = sum(p["revenue"] for p in peers) or me["revenue"]
    market_share = round(me["revenue"] / total_rev * 100, 2) if total_rev else None
    industry_rev_growth = float(profile.revenue_growth_3y_cagr) if profile and profile.revenue_growth_3y_cagr is not None else (me["revenue_growth"] or 0.0)
    peer_median_margin = float(profile.median_operating_margin) if profile and profile.median_operating_margin is not None else (me["operating_margin"] or 0.0)
    hhi = float(structure.hhi_index) if structure and structure.hhi_index is not None else 0.0

    # ── Moat ──────────────────────────────────────────────────────────
    moat = moat_engine.assess_moat(
        roic_history=[me["roic"]] if me["roic"] is not None else [],
        wacc_history=[me["wacc"]] if me["wacc"] is not None else [],
        margin_history=me["gross_margin_history"],
        entity_revenue_growth=me["revenue_growth"] or 0.0,
        industry_revenue_growth=industry_rev_growth,
        peer_median_margin=peer_median_margin,
        operating_margin=me["operating_margin"] or 0.0,
        capex_intensity=me["capex_intensity"],
        recurring_pct=0.0,
        hhi=hhi,
        market_share=market_share or 0.0,
    )
    await _upsert_competitive(session, MoatAssessment, entity_id, today, dict(
        roic_above_wacc_years=moat.roic_above_wacc_years,
        moat_width=moat.moat_width, moat_stability=moat.moat_stability, moat_score=moat.moat_score,
        cost_advantage_score=moat.cost_advantage_score, network_effects_score=moat.network_effects_score,
        switching_costs_score=moat.switching_costs_score, intangible_assets_score=moat.intangible_assets_score,
        efficient_scale_score=moat.efficient_scale_score, dominant_moat_source=moat.dominant_source,
        moat_evidence={"evidence": moat.evidence}, ai_enabled=False,
    ))

    # ── Competitive landscape ─────────────────────────────────────────
    entity_data = {
        "entity_id": str(entity_id), "name": entity.legal_name,
        "gics_sector": entity.gics_sector, "gics_industry": entity.gics_industry,
        "market_cap": None, "revenue": me["revenue"], "revenue_growth": me["revenue_growth"],
        "operating_margin": me["operating_margin"], "roic": me["roic"], "market_share": market_share,
    }
    industry_stats = {
        "median_operating_margin": peer_median_margin,
        "median_roic": float(profile.median_roic) if profile and profile.median_roic is not None else None,
        "revenue_growth": industry_rev_growth,
    }
    land = cl_engine.analyze_competitive_landscape(entity_data, peers or [entity_data], industry_stats)
    await _upsert_competitive(session, CompetitiveLandscape, entity_id, today, dict(
        gics_code=gics_code or "",
        peer_group=[asdict(p) for p in land.peer_group],
        market_share_est_pct=land.market_share_est, market_share_rank=land.entity_rank,
        revenue_growth_vs_peers=land.revenue_growth_vs_peers, margin_vs_peers=land.margin_vs_peers,
        roic_vs_peers=land.roic_vs_peers, share_gainer=land.share_gainer,
        value_chain_position=land.value_chain_position,
        competitive_advantages=land.competitive_advantages, competitive_threats=land.competitive_threats,
    ))

    # ── Concentration risk (from business_relationships + segments) ───
    rels = (await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.source_entity_id == entity_id,
            BusinessRelationship.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    customer_pcts = [
        float(r.revenue_percentage) for r in rels
        if r.relationship_type == "CUSTOMER" and r.revenue_percentage is not None
    ]
    suppliers = [r for r in rels if r.relationship_type == "SUPPLIER"]
    customer_pcts.sort(reverse=True)
    customer_data = {
        "top1_pct": customer_pcts[0] if customer_pcts else None,
        "customer_pcts": customer_pcts or None,
    }
    supplier_data = {
        "single_source_count": sum(1 for s in suppliers if s.is_single_source),
        "critical_count": sum(1 for s in suppliers if (s.materiality_score or 0) and float(s.materiality_score) >= 0.7),
        "geographic_spread": 0,
    }
    seg_rows = (await session.execute(
        select(SegmentData.segment_name, SegmentData.revenue)
        .where(SegmentData.entity_id == entity_id, SegmentData.segment_type == "GEOGRAPHIC")
    )).all()
    revenue_by_region = {n: float(r) for n, r in seg_rows if r is not None}
    conc = cr_engine.assess_concentration_risk(
        customer_data, supplier_data, {"revenue_by_region": revenue_by_region},
    )
    await _upsert_competitive(session, ConcentrationRiskAssessment, entity_id, today, dict(
        customer_top1_pct=conc.customer_top1_pct, customer_concentration_risk=conc.customer_risk,
        supplier_single_source_count=conc.supplier_single_source_count,
        supplier_concentration_risk=conc.supplier_risk,
        geographic_revenue_breakdown=revenue_by_region or None,
        geographic_hhi=conc.geographic_hhi, fx_exposure_score=conc.fx_exposure_score,
        geographic_concentration_risk=conc.geographic_risk,
        overall_concentration_risk=conc.overall_risk, overall_risk_score=conc.overall_score,
    ))

    await session.commit()
    return True


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
    entity = await _get_entity(session, entity_id)

    async def _q():
        return (await session.execute(
            select(MoatAssessment).where(MoatAssessment.entity_id == entity_id)
            .order_by(MoatAssessment.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_competitive(session, entity):
        row = await _q()
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
    entity = await _get_entity(session, entity_id)

    async def _q():
        return (await session.execute(
            select(ConcentrationRiskAssessment).where(ConcentrationRiskAssessment.entity_id == entity_id)
            .order_by(ConcentrationRiskAssessment.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_competitive(session, entity):
        row = await _q()
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
    entity = await _get_entity(session, entity_id)

    async def _q():
        return (await session.execute(
            select(CompetitiveLandscape).where(CompetitiveLandscape.entity_id == entity_id)
            .order_by(CompetitiveLandscape.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_competitive(session, entity):
        row = await _q()
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
