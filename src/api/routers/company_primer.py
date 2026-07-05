"""Company Primer API endpoints (Pillar 2 Supplement – Part 7)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.deps import get_session
from src.engines.company_primer import (
    compute_financial_summary,
    compute_valuation_summary,
    compute_ownership_summary,
    extract_key_risks,
    generate_primer,
)
from src.models.company_intelligence import CompanyPrimer
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod  # noqa: F401 — relationships load IncomeStatement etc.
from src.models.analytics import AnalyticsResult
from src.schemas.company_intelligence import (
    CompanyPrimerResponse,
    FinancialSummaryResponse,
)

router = APIRouter(tags=["Company Primer"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    """Fetch entity or raise 404."""
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get(
    "/analytics/primer/{entity_id}",
    response_model=CompanyPrimerResponse,
)
async def get_company_primer(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a one-page company primer.

    Generates if not found. AI text sections are null when AI is disabled.
    """
    entity = await _get_entity(session, entity_id)

    # Check for existing primer
    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.generated_date.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _primer_to_response(existing)

    # R-013: Populate data dicts from DB before calling generate_primer()
    llm = get_llm_client()

    # Fetch latest financial period with related statements
    fp_result = await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(1)
    )
    latest_period = fp_result.scalar_one_or_none()

    financial_data: dict = {}
    risk_data: dict = {}
    if latest_period:
        inc = latest_period.income_statement
        bs = latest_period.balance_sheet
        cf = latest_period.cash_flow
        if inc:
            financial_data["revenue"] = float(inc.total_revenue) if inc.total_revenue is not None else None
            financial_data["ebitda"] = float(inc.ebitda) if inc.ebitda is not None else None
            financial_data["net_income"] = float(inc.net_income) if inc.net_income is not None else None
            financial_data["eps"] = float(inc.diluted_eps) if inc.diluted_eps is not None else None
        if bs:
            financial_data["total_debt"] = float(bs.total_debt) if bs.total_debt is not None else None
            financial_data["total_equity"] = float(bs.total_equity) if bs.total_equity is not None else None
            # Risk: leverage
            if bs.total_debt is not None and bs.total_equity is not None and bs.total_equity > 0:
                risk_data["debt_to_equity"] = float(bs.total_debt) / float(bs.total_equity)
        if cf:
            financial_data["free_cash_flow"] = float(cf.free_cash_flow) if cf.free_cash_flow is not None else None
        if inc and inc.operating_income is not None and inc.interest_expense is not None and inc.interest_expense != 0:
            risk_data["interest_coverage"] = float(inc.operating_income) / abs(float(inc.interest_expense))

    # Fetch valuation metrics from analytics results
    valuation_data: dict = {}
    val_result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.metric_category == "VALUATION",
        )
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(10)
    )
    for ar in val_result.scalars().all():
        name = ar.metric_name.lower()
        if ar.value is not None and name not in valuation_data:
            valuation_data[name] = float(ar.value)

    # Ownership data -- left empty since OwnershipSummary is keyed by
    # security_id and we only have entity_id here; a full join through
    # securities could be added later.
    ownership_data: dict = {}

    primer = generate_primer(
        entity_id=str(entity_id),
        entity_name=entity.legal_name,
        financial_data=financial_data,
        valuation_data=valuation_data,
        ownership_data=ownership_data,
        risk_data=risk_data,
        ai_description=None,
        ai_competitive=None,
    )

    db_primer = CompanyPrimer(
        primer_id=uuid.uuid4(),
        entity_id=entity_id,
        generated_date=date.today(),
        business_description=primer.business_description,
        segments_breakdown=primer.segments_breakdown,
        competitive_position=primer.competitive_position,
        financial_summary=primer.financial_summary,
        valuation_summary=primer.valuation_summary,
        ownership_summary=primer.ownership_summary,
        key_risks=primer.key_risks,
        recent_developments=primer.recent_developments,
        ai_enabled=primer.ai_enabled,
    )
    session.add(db_primer)
    await session.commit()
    await session.refresh(db_primer)

    return _primer_to_response(db_primer)


@router.get(
    "/analytics/primer/{entity_id}/financials",
    response_model=FinancialSummaryResponse,
)
async def get_financial_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get financial summary only (no AI needed)."""
    await _get_entity(session, entity_id)

    # R-013: Populate financial and valuation data from DB
    fp_result = await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(1)
    )
    latest_period = fp_result.scalar_one_or_none()

    financial_data: dict = {}
    if latest_period:
        inc = latest_period.income_statement
        bs = latest_period.balance_sheet
        cf = latest_period.cash_flow
        if inc:
            financial_data["revenue"] = float(inc.total_revenue) if inc.total_revenue is not None else None
            financial_data["ebitda"] = float(inc.ebitda) if inc.ebitda is not None else None
            financial_data["net_income"] = float(inc.net_income) if inc.net_income is not None else None
            financial_data["eps"] = float(inc.diluted_eps) if inc.diluted_eps is not None else None
        if bs:
            financial_data["total_debt"] = float(bs.total_debt) if bs.total_debt is not None else None
            financial_data["total_equity"] = float(bs.total_equity) if bs.total_equity is not None else None
        if cf:
            financial_data["free_cash_flow"] = float(cf.free_cash_flow) if cf.free_cash_flow is not None else None

    valuation_data: dict = {}
    val_result = await session.execute(
        select(AnalyticsResult)
        .where(
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.metric_category == "VALUATION",
        )
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(10)
    )
    for ar in val_result.scalars().all():
        name = ar.metric_name.lower()
        if ar.value is not None and name not in valuation_data:
            valuation_data[name] = float(ar.value)

    return FinancialSummaryResponse(
        entity_id=entity_id,
        financial_summary=compute_financial_summary(financial_data),
        valuation_summary=compute_valuation_summary(valuation_data),
        generated_at=datetime.now(timezone.utc),
    )


def _primer_to_response(primer: CompanyPrimer) -> CompanyPrimerResponse:
    """Convert a DB primer to response schema."""
    return CompanyPrimerResponse(
        primer_id=primer.primer_id,
        entity_id=primer.entity_id,
        generated_date=primer.generated_date,
        business_description=primer.business_description,
        segments_breakdown=primer.segments_breakdown,
        competitive_position=primer.competitive_position,
        financial_summary=primer.financial_summary,
        valuation_summary=primer.valuation_summary,
        ownership_summary=primer.ownership_summary,
        key_risks=primer.key_risks,
        recent_developments=primer.recent_developments,
        ai_enabled=primer.ai_enabled,
    )
