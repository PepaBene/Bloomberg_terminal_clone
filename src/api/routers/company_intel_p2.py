"""Company Intelligence P2 API endpoints (Pillar 3 Phase 2)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.company_intelligence import (
    BalanceSheetRiskAssessment,
    BusinessModelAnalysis,
    CapitalAllocationAssessment,
    ManagementQualityAssessment,
)
from src.schemas.company_intelligence_p2 import (
    BalanceSheetRiskResponse,
    BusinessModelResponse,
    CapitalAllocationResponse,
    CompanyIntelligenceResponse,
    ManagementQualityResponse,
)

router = APIRouter(tags=["Company Intelligence"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# ── Full Intelligence Report ──────────────────────────────────────────


@router.get(
    "/company/{entity_id}/intelligence",
    response_model=CompanyIntelligenceResponse,
)
async def get_company_intelligence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get full company intelligence report."""
    await _get_entity(session, entity_id)

    # Fetch latest from each sub-assessment
    bma_result = await session.execute(
        select(BusinessModelAnalysis)
        .where(BusinessModelAnalysis.entity_id == entity_id)
        .order_by(BusinessModelAnalysis.as_of_date.desc())
        .limit(1)
    )
    bma = bma_result.scalar_one_or_none()

    caa_result = await session.execute(
        select(CapitalAllocationAssessment)
        .where(CapitalAllocationAssessment.entity_id == entity_id)
        .order_by(CapitalAllocationAssessment.as_of_date.desc())
        .limit(1)
    )
    caa = caa_result.scalar_one_or_none()

    mqa_result = await session.execute(
        select(ManagementQualityAssessment)
        .where(ManagementQualityAssessment.entity_id == entity_id)
        .order_by(ManagementQualityAssessment.as_of_date.desc())
        .limit(1)
    )
    mqa = mqa_result.scalar_one_or_none()

    bsra_result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    bsra = bsra_result.scalar_one_or_none()

    # Build summary
    ai_summaries = []
    if bma and bma.ai_summary:
        ai_summaries.append(bma.ai_summary)
    if caa and caa.ai_summary:
        ai_summaries.append(caa.ai_summary)
    if mqa and mqa.ai_summary:
        ai_summaries.append(mqa.ai_summary)
    if bsra and bsra.ai_summary:
        ai_summaries.append(bsra.ai_summary)

    return CompanyIntelligenceResponse(
        entity_id=entity_id,
        business_model={
            "recurring_pct": float(bma.recurring_pct) if bma and bma.recurring_pct else None,
            "moat_type": bma.moat_type if bma else None,
            "operating_leverage": float(bma.operating_leverage) if bma and bma.operating_leverage else None,
        } if bma else None,
        capital_allocation={
            "overall_score": float(caa.overall_score) if caa and caa.overall_score else None,
            "roic_vs_wacc_spread": float(caa.roic_vs_wacc_spread) if caa and caa.roic_vs_wacc_spread else None,
        } if caa else None,
        management_quality={
            "execution_score": float(mqa.execution_score) if mqa and mqa.execution_score else None,
            "governance_score": float(mqa.governance_score) if mqa and mqa.governance_score else None,
            "overall_quality_score": float(mqa.overall_quality_score) if mqa and mqa.overall_quality_score else None,
        } if mqa else None,
        balance_sheet_risk={
            "net_debt_ebitda": float(bsra.net_debt_ebitda) if bsra and bsra.net_debt_ebitda else None,
            "refinancing_risk_score": float(bsra.refinancing_risk_score) if bsra and bsra.refinancing_risk_score else None,
            "z_score": float(bsra.z_score) if bsra and bsra.z_score else None,
        } if bsra else None,
        governance_score=float(mqa.governance_score) if mqa and mqa.governance_score else None,
        ai_summary=" | ".join(ai_summaries) if ai_summaries else None,
    )


@router.get(
    "/company/{entity_id}/intelligence/summary",
    response_model=CompanyIntelligenceResponse,
)
async def get_company_intelligence_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get AI-generated intelligence summary for a company."""
    # Delegates to the full report (same data, frontend consumes ai_summary)
    return await get_company_intelligence(entity_id, session)


# ── Business Model ────────────────────────────────────────────────────


@router.get(
    "/company/{entity_id}/business-model",
    response_model=BusinessModelResponse,
)
async def get_business_model(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get business model analysis for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BusinessModelAnalysis)
        .where(BusinessModelAnalysis.entity_id == entity_id)
        .order_by(BusinessModelAnalysis.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No business model analysis found")

    return BusinessModelResponse(
        entity_id=r.entity_id,
        revenue_quality={
            "recurring_pct": float(r.recurring_pct) if r.recurring_pct is not None else None,
            "customer_concentration": float(r.customer_concentration) if r.customer_concentration is not None else None,
            "diversification_score": float(r.diversification_score) if r.diversification_score is not None else None,
            "cyclicality_score": float(r.cyclicality_score) if r.cyclicality_score is not None else None,
            "revenue_per_employee": float(r.revenue_per_employee) if r.revenue_per_employee is not None else None,
        },
        unit_economics=r.unit_economics,
        scaling={
            "operating_leverage": float(r.operating_leverage) if r.operating_leverage is not None else None,
            "incremental_margin": float(r.incremental_margin) if r.incremental_margin is not None else None,
            "sga_scalability": float(r.sga_scalability) if r.sga_scalability is not None else None,
        },
        durability={
            "moat_type": r.moat_type,
            "switching_cost_score": float(r.switching_cost_score) if r.switching_cost_score is not None else None,
            "disruption_vulnerability": float(r.disruption_vulnerability) if r.disruption_vulnerability is not None else None,
        },
        ai_summary=r.ai_summary,
    )


@router.get(
    "/company/{entity_id}/business-model/segments",
    response_model=dict,
)
async def get_business_segments(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get revenue segment breakdown for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BusinessModelAnalysis)
        .where(BusinessModelAnalysis.entity_id == entity_id)
        .order_by(BusinessModelAnalysis.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No business model analysis found")

    return {
        "entity_id": str(r.entity_id),
        "revenue_decomposition": r.revenue_decomposition,
        "deferred_revenue_trend": r.deferred_revenue_trend,
    }


# ── Capital Allocation ────────────────────────────────────────────────


@router.get(
    "/company/{entity_id}/capital-allocation",
    response_model=CapitalAllocationResponse,
)
async def get_capital_allocation(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get capital allocation assessment for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CapitalAllocationAssessment)
        .where(CapitalAllocationAssessment.entity_id == entity_id)
        .order_by(CapitalAllocationAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No capital allocation assessment found")

    return CapitalAllocationResponse(
        entity_id=r.entity_id,
        fcf_conversion=float(r.ebitda_to_fcf_conversion) if r.ebitda_to_fcf_conversion is not None else None,
        working_capital=r.working_capital_discipline,
        roic_vs_wacc={
            "spread": float(r.roic_vs_wacc_spread) if r.roic_vs_wacc_spread is not None else None,
            "history": r.roic_vs_wacc_history,
        },
        ma_discipline=r.ma_discipline,
        buyback_effectiveness=r.buyback_effectiveness,
        dividend_sustainability=r.dividend_sustainability,
        overall_score=float(r.overall_score) if r.overall_score is not None else None,
    )


@router.get(
    "/company/{entity_id}/capital-allocation/ma-history",
    response_model=dict,
)
async def get_ma_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get M&A discipline history for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CapitalAllocationAssessment)
        .where(CapitalAllocationAssessment.entity_id == entity_id)
        .order_by(CapitalAllocationAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No capital allocation assessment found")

    return {
        "entity_id": str(r.entity_id),
        "ma_discipline": r.ma_discipline,
    }


@router.get(
    "/company/{entity_id}/capital-allocation/buybacks",
    response_model=dict,
)
async def get_buybacks(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get buyback effectiveness for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CapitalAllocationAssessment)
        .where(CapitalAllocationAssessment.entity_id == entity_id)
        .order_by(CapitalAllocationAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No capital allocation assessment found")

    return {
        "entity_id": str(r.entity_id),
        "buyback_effectiveness": r.buyback_effectiveness,
    }


# ── Management Quality ────────────────────────────────────────────────


@router.get(
    "/company/{entity_id}/management",
    response_model=ManagementQualityResponse,
)
async def get_management_quality(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get management quality assessment for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ManagementQualityAssessment)
        .where(ManagementQualityAssessment.entity_id == entity_id)
        .order_by(ManagementQualityAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No management quality assessment found")

    accounting_flags = []
    if r.auditor_change_flag:
        accounting_flags.append({"flag": "AUDITOR_CHANGE", "severity": "WARNING"})
    if r.restatement_flag:
        accounting_flags.append({"flag": "RESTATEMENT", "severity": "HIGH"})

    return ManagementQualityResponse(
        entity_id=r.entity_id,
        execution_score=float(r.execution_score) if r.execution_score is not None else None,
        governance_score=float(r.governance_score) if r.governance_score is not None else None,
        accounting_flags=accounting_flags if accounting_flags else None,
        compensation_alignment=r.compensation_alignment,
        overall_score=float(r.overall_quality_score) if r.overall_quality_score is not None else None,
        red_flags=r.red_flags if isinstance(r.red_flags, list) else None,
    )


@router.get(
    "/company/{entity_id}/governance",
    response_model=ManagementQualityResponse,
)
async def get_governance(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get governance assessment (delegates to management quality)."""
    return await get_management_quality(entity_id, session)


@router.get(
    "/company/{entity_id}/governance/red-flags",
    response_model=dict,
)
async def get_governance_red_flags(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get governance red flags for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ManagementQualityAssessment)
        .where(ManagementQualityAssessment.entity_id == entity_id)
        .order_by(ManagementQualityAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No management quality assessment found")

    flags = []
    if r.auditor_change_flag:
        flags.append({"flag": "AUDITOR_CHANGE", "severity": "WARNING"})
    if r.restatement_flag:
        flags.append({"flag": "RESTATEMENT", "severity": "HIGH"})
    if r.red_flags and isinstance(r.red_flags, list):
        flags.extend(r.red_flags)

    return {
        "entity_id": str(r.entity_id),
        "red_flags": flags,
        "beneish_m_score": float(r.beneish_m_score) if r.beneish_m_score is not None else None,
        "accruals_quality": float(r.accruals_quality) if r.accruals_quality is not None else None,
    }


# ── Balance Sheet Risk ────────────────────────────────────────────────


@router.get(
    "/company/{entity_id}/balance-sheet-risk",
    response_model=BalanceSheetRiskResponse,
)
async def get_balance_sheet_risk(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get balance sheet risk assessment for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    return BalanceSheetRiskResponse(
        entity_id=r.entity_id,
        leverage={
            "net_debt_ebitda": float(r.net_debt_ebitda) if r.net_debt_ebitda is not None else None,
            "net_debt_ebitda_trend": r.net_debt_ebitda_trend,
            "interest_coverage": float(r.interest_coverage) if r.interest_coverage is not None else None,
            "interest_coverage_trend": r.interest_coverage_trend,
        },
        liquidity={
            "liquidity_ratio": float(r.liquidity_ratio) if r.liquidity_ratio is not None else None,
            "cash_burn_rate": float(r.cash_burn_rate) if r.cash_burn_rate is not None else None,
        },
        refinancing_risk_score=float(r.refinancing_risk_score) if r.refinancing_risk_score is not None else None,
        z_score=float(r.z_score) if r.z_score is not None else None,
        fi_profile=r.fi_profile,
        ai_summary=r.ai_summary,
    )


@router.get(
    "/company/{entity_id}/debt-maturity",
    response_model=dict,
)
async def get_debt_maturity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get debt maturity profile for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    return {
        "entity_id": str(r.entity_id),
        "maturity_24mo_pct": float(r.maturity_24mo_pct) if r.maturity_24mo_pct is not None else None,
        "coverage_trend": r.coverage_trend,
        "covenant_analysis": r.covenant_analysis,
    }


@router.get(
    "/company/{entity_id}/refinancing-risk",
    response_model=dict,
)
async def get_refinancing_risk(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get refinancing risk score for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    return {
        "entity_id": str(r.entity_id),
        "refinancing_risk_score": float(r.refinancing_risk_score) if r.refinancing_risk_score is not None else None,
        "maturity_24mo_pct": float(r.maturity_24mo_pct) if r.maturity_24mo_pct is not None else None,
        "interest_coverage": float(r.interest_coverage) if r.interest_coverage is not None else None,
    }


# ── FI Profile ────────────────────────────────────────────────────────


@router.get(
    "/company/{entity_id}/fi-profile",
    response_model=dict,
)
async def get_fi_profile(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get fixed-income issuer profile for a company."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    return {
        "entity_id": str(r.entity_id),
        "fi_profile": r.fi_profile,
        "z_score": float(r.z_score) if r.z_score is not None else None,
        "refinancing_risk_score": float(r.refinancing_risk_score) if r.refinancing_risk_score is not None else None,
    }


@router.get(
    "/company/{entity_id}/fi-profile/bonds",
    response_model=dict,
)
async def get_fi_bonds(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get bond information from FI profile."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    fi = r.fi_profile or {}
    return {
        "entity_id": str(r.entity_id),
        "bonds": fi.get("bonds", []),
        "total_debt_outstanding": fi.get("total_debt_outstanding"),
    }


@router.get(
    "/company/{entity_id}/fi-profile/ratings",
    response_model=dict,
)
async def get_fi_ratings(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get credit ratings from FI profile."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    fi = r.fi_profile or {}
    return {
        "entity_id": str(r.entity_id),
        "ratings": fi.get("ratings", {}),
        "z_score": float(r.z_score) if r.z_score is not None else None,
    }


@router.get(
    "/company/{entity_id}/fi-profile/maturity-wall",
    response_model=dict,
)
async def get_fi_maturity_wall(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get debt maturity wall from FI profile."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    fi = r.fi_profile or {}
    return {
        "entity_id": str(r.entity_id),
        "maturity_wall": fi.get("maturity_wall", []),
        "maturity_24mo_pct": float(r.maturity_24mo_pct) if r.maturity_24mo_pct is not None else None,
    }


@router.get(
    "/company/{entity_id}/fi-profile/market-cost-debt",
    response_model=dict,
)
async def get_fi_market_cost_debt(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get market-implied cost of debt from FI profile."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(BalanceSheetRiskAssessment)
        .where(BalanceSheetRiskAssessment.entity_id == entity_id)
        .order_by(BalanceSheetRiskAssessment.as_of_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="No balance sheet risk assessment found")

    fi = r.fi_profile or {}
    return {
        "entity_id": str(r.entity_id),
        "market_cost_of_debt": fi.get("market_cost_of_debt"),
        "spread_to_benchmark": fi.get("spread_to_benchmark"),
        "interest_coverage": float(r.interest_coverage) if r.interest_coverage is not None else None,
    }
