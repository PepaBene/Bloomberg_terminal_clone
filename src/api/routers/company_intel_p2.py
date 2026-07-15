"""Company Intelligence P2 API endpoints (Pillar 3 Phase 2)."""

import uuid
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import (
    balance_sheet_risk_engine,
    business_model_engine,
    capital_allocation_engine,
    management_quality_engine,
)
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.company_intelligence import (
    BalanceSheetRiskAssessment,
    BusinessModelAnalysis,
    CapitalAllocationAssessment,
    ManagementQualityAssessment,
)
from src.models.fundamentals import FinancialPeriod, SegmentData  # noqa: F401 — relationships load statements
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


def _f(v):
    return float(v) if v is not None else None


async def _assemble_fundamentals(session: AsyncSession, entity_id: uuid.UUID) -> dict | None:
    """Assemble the financials/history/analytics inputs the four deep-
    intelligence engines consume, from real Pillar 1/2 data. Returns None
    when the entity has no fundamentals to analyze.

    The engines read their inputs via ``.get(...)`` and default gracefully,
    so fields with no ingested source (e.g. recurring_revenue_pct,
    guidance history, insider ownership) are simply omitted rather than
    fabricated.
    """
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

    def _period_dict(p) -> dict:
        inc, bs, cf = p.income_statement, p.balance_sheet, p.cash_flow
        rev = float(inc.total_revenue) if inc and inc.total_revenue is not None else None
        d: dict = {"period_end_date": p.period_end_date.isoformat()}
        if inc:
            d["revenue"] = rev
            d["cogs"] = _f(inc.cost_of_revenue)
            d["operating_income"] = _f(inc.operating_income)
            d["net_income"] = _f(inc.net_income)
            d["ebitda"] = _f(inc.ebitda)
            d["sga"] = _f(inc.selling_general_admin)
            d["depreciation"] = _f(inc.depreciation_amortization)
            d["interest_expense"] = _f(inc.interest_expense)
            d["eps"] = _f(inc.diluted_eps)
            d["shares"] = _f(inc.diluted_shares_outstanding)
            if rev and inc.gross_profit is not None:
                d["gross_margin"] = round(float(inc.gross_profit) / rev * 100, 2)
        if bs:
            d["total_debt"] = _f(bs.total_debt)
            d["cash"] = _f(bs.cash_and_equivalents)
            d["total_assets"] = _f(bs.total_assets)
            d["total_equity"] = _f(bs.total_equity)
            d["receivables"] = _f(bs.accounts_receivable)
            d["inventory"] = _f(bs.inventory)
            d["payables"] = _f(bs.accounts_payable)
            d["total_current_assets"] = _f(bs.total_current_assets)
            d["total_current_liabilities"] = _f(bs.total_current_liabilities)
        if cf:
            d["capex"] = abs(float(cf.capital_expenditures)) if cf.capital_expenditures is not None else None
            d["fcf"] = _f(cf.free_cash_flow)
            d["dividends_paid"] = _f(cf.dividends_paid)
        # Derived leverage figures the balance-sheet engine reads per period.
        if d.get("total_debt") is not None and d.get("ebitda"):
            d["net_debt_ebitda"] = round((d["total_debt"] - (d.get("cash") or 0.0)) / d["ebitda"], 4)
        if d.get("operating_income") is not None and d.get("interest_expense"):
            d["interest_coverage"] = round(d["operating_income"] / abs(d["interest_expense"]), 4)
        return d

    history = [_period_dict(p) for p in periods]
    financials = dict(history[-1])  # latest period is the "current" snapshot

    # ROIC / WACC from batch analytics (latest values).
    metrics = {}
    rows = (
        await session.execute(
            select(AnalyticsResult.metric_name, AnalyticsResult.value, AnalyticsResult.as_of_date)
            .where(
                AnalyticsResult.entity_id == entity_id,
                AnalyticsResult.metric_name.in_(
                    ["roic", "wacc", "beneish_m_score", "altman_z_score"]
                ),
            )
            .order_by(AnalyticsResult.as_of_date.desc())
        )
    ).all()
    for name, value, _asof in rows:
        if value is not None and name not in metrics:
            metrics[name] = float(value)
    if "roic" in metrics:
        financials["roic"] = metrics["roic"]
    if "beneish_m_score" in metrics:
        financials["beneish_m_score"] = metrics["beneish_m_score"]
    if "altman_z_score" in metrics:
        financials["z_score"] = metrics["altman_z_score"]

    # Derived history series the engines look for.
    gross_margin_history = [h["gross_margin"] for h in history if h.get("gross_margin") is not None]
    margin_history = [
        round(h["operating_income"] / h["revenue"] * 100, 2)
        for h in history
        if h.get("operating_income") is not None and h.get("revenue")
    ]
    revenue_history = [h["revenue"] for h in history if h.get("revenue") is not None]
    financials["gross_margin_history"] = gross_margin_history
    financials["revenue_history"] = revenue_history
    financials["roic_history"] = [metrics["roic"]] if "roic" in metrics else []

    # Segment counts / decomposition (business model inputs).
    seg_rows = (
        await session.execute(
            select(SegmentData.segment_name, SegmentData.segment_type, SegmentData.revenue)
            .where(SegmentData.entity_id == entity_id)
            .limit(100)
        )
    ).all()
    product_segments = [(n, r) for n, t, r in seg_rows if t == "BUSINESS"]
    geo_segments = [(n, r) for n, t, r in seg_rows if t == "GEOGRAPHIC"]
    financials["product_segment_count"] = len({n for n, _ in product_segments})
    financials["geo_segment_count"] = len({n for n, _ in geo_segments})
    financials["segments"] = [
        {"name": n, "revenue": float(r) if r is not None else None} for n, r in product_segments
    ]

    return {
        "financials": financials,
        "history": history,
        "gross_margin_history": gross_margin_history,
        "margin_history": margin_history,
        "roic": metrics.get("roic"),
        "wacc": metrics.get("wacc"),
    }


async def _compute_and_persist_intelligence(session: AsyncSession, entity_id: uuid.UUID) -> bool:
    """Compute all four deep-intelligence assessments from real data and
    upsert today's rows. Returns False when there's no fundamentals to
    analyze (nothing persisted). This is the missing producer for the four
    company_intelligence tables — the engines existed but had no caller."""
    assembled = await _assemble_fundamentals(session, entity_id)
    if assembled is None:
        return False

    financials = assembled["financials"]
    history = assembled["history"]
    today = date.today()

    # ── Business model ────────────────────────────────────────────────
    bm = business_model_engine.analyze_business_model(financials, history)
    ue = asdict(bm.unit_economics)
    await _upsert(session, BusinessModelAnalysis, entity_id, today, dict(
        recurring_pct=bm.revenue_quality.recurring_pct,
        deferred_revenue_trend=bm.revenue_quality.deferred_revenue_trend,
        customer_concentration=bm.revenue_quality.customer_concentration,
        diversification_score=bm.revenue_quality.diversification_score,
        cyclicality_score=bm.revenue_quality.cyclicality_score,
        revenue_per_employee=bm.unit_economics.revenue_per_employee,
        unit_economics=ue,
        operating_leverage=bm.scaling.operating_leverage,
        incremental_margin=bm.scaling.incremental_margin,
        sga_scalability=bm.scaling.sga_scalability,
        switching_cost_score=bm.durability.switching_cost_score,
        moat_type=bm.durability.moat_type,
        disruption_vulnerability=bm.durability.disruption_vulnerability,
        # E-017: surface whether cyclicality_score is a real measurement or
        # the 50.0 neutral default (< 3 periods of revenue_history).
        revenue_decomposition={
            "segments": financials.get("segments", []),
            "cyclicality_data_sufficient": bm.revenue_quality.cyclicality_data_sufficient,
        },
        ai_enabled=False,
    ))

    # ── Capital allocation ────────────────────────────────────────────
    ca = capital_allocation_engine.analyze_capital_allocation(financials)
    spread = None
    if assembled["roic"] is not None and assembled["wacc"] is not None:
        spread = round(assembled["roic"] - assembled["wacc"], 4)
    await _upsert(session, CapitalAllocationAssessment, entity_id, today, dict(
        ebitda_to_fcf_conversion=ca.fcf_conversion.ebitda_to_fcf_ratio,
        maintenance_capex_pct=ca.capex.maintenance_capex_revenue_pct,
        growth_capex_pct=ca.capex.growth_capex_revenue_pct,
        working_capital_discipline=asdict(ca.working_capital),
        roic_vs_wacc_spread=spread,
        ma_discipline=asdict(ca.ma_discipline),
        buyback_effectiveness=asdict(ca.buybacks),
        dividend_sustainability=asdict(ca.dividends),
        overall_score=ca.overall_score,
        ai_enabled=False,
    ))

    # ── Balance sheet risk ────────────────────────────────────────────
    bsr = balance_sheet_risk_engine.assess_balance_sheet_risk(financials, history)
    await _upsert(session, BalanceSheetRiskAssessment, entity_id, today, dict(
        net_debt_ebitda=bsr.leverage.net_debt_ebitda,
        net_debt_ebitda_trend=bsr.leverage.net_debt_ebitda_trend,
        interest_coverage=bsr.leverage.interest_coverage,
        interest_coverage_trend=bsr.leverage.interest_coverage_trend,
        liquidity_ratio=bsr.liquidity.liquidity_ratio,
        cash_burn_rate=bsr.liquidity.cash_burn_rate,
        refinancing_risk_score=bsr.refinancing_risk.score,
        maturity_24mo_pct=bsr.refinancing_risk.maturity_24mo_pct,
        coverage_trend=bsr.refinancing_risk.coverage_trend,
        z_score=bsr.refinancing_risk.z_score,
        covenant_analysis=bsr.refinancing_risk.components,
        fi_profile=asdict(bsr.fi_profile) if bsr.fi_profile else None,
        ai_enabled=False,
    ))

    # ── Management quality ────────────────────────────────────────────
    mq = management_quality_engine.assess_management_quality(
        financials, margin_history=assembled["margin_history"]
    )
    await _upsert(session, ManagementQualityAssessment, entity_id, today, dict(
        guidance_accuracy_score=mq.execution.guidance_accuracy_score,
        strategic_consistency_score=mq.execution.strategic_consistency_score,
        margin_stability_score=mq.execution.margin_stability_score,
        wc_management_score=mq.execution.wc_management_score,
        execution_score=mq.execution.composite_execution_score,
        compensation_alignment=asdict(mq.compensation) if mq.compensation else None,
        governance_score=mq.governance_score,
        overall_quality_score=mq.overall_quality_score,
        red_flags={"flags": [asdict(f) for f in mq.accounting_flags] + list(mq.red_flags or [])},
        ai_enabled=False,
    ))

    await session.commit()
    return True


async def _upsert(session, model, entity_id, as_of, values: dict) -> None:
    """Upsert a per-entity/per-day assessment row."""
    existing = (
        await session.execute(
            select(model).where(model.entity_id == entity_id, model.as_of_date == as_of)
        )
    ).scalar_one_or_none()
    if existing is not None:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(model(id=uuid.uuid4(), entity_id=entity_id, as_of_date=as_of, **values))


# ── Full Intelligence Report ──────────────────────────────────────────


@router.get(
    "/company/{entity_id}/intelligence",
    response_model=CompanyIntelligenceResponse,
)
async def get_company_intelligence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get full company intelligence report.

    Computes the four deep-intelligence assessments on-demand from real
    Pillar 1/2 data when none exist yet, then persists and returns them —
    the tables previously had no producer, so this always returned all-null.
    """
    await _get_entity(session, entity_id)

    # Fetch latest from each sub-assessment
    bma_result = await session.execute(
        select(BusinessModelAnalysis)
        .where(BusinessModelAnalysis.entity_id == entity_id)
        .order_by(BusinessModelAnalysis.as_of_date.desc())
        .limit(1)
    )
    bma = bma_result.scalar_one_or_none()

    if bma is None:
        # No assessment yet — compute from real fundamentals on-demand.
        if await _compute_and_persist_intelligence(session, entity_id):
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
        ai_summary="\n\n".join(ai_summaries) if ai_summaries else None,
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


@router.post(
    "/company/{entity_id}/intelligence/refresh",
    response_model=CompanyIntelligenceResponse,
)
async def refresh_company_intelligence(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Force-recompute all four deep-intelligence assessments from the latest
    fundamentals and return the refreshed report."""
    await _get_entity(session, entity_id)
    computed = await _compute_and_persist_intelligence(session, entity_id)
    if not computed:
        raise HTTPException(
            status_code=422,
            detail="No fundamentals available to compute company intelligence for this entity",
        )
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
