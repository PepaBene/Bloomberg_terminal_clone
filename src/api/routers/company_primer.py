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
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
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


async def _assemble_financial_data(
    session: AsyncSession, entity_id: uuid.UUID
) -> dict:
    """Pull the latest IS/BS/CF rows for a company so generate_primer has
    real numbers to work with instead of empty dicts. Returns whatever the
    DB has — missing periods are simply absent from the result.
    """
    period_row = await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(1)
    )
    period = period_row.scalar_one_or_none()
    if not period:
        return {}

    is_row = await session.execute(
        select(IncomeStatement).where(IncomeStatement.period_id == period.period_id)
    )
    bs_row = await session.execute(
        select(BalanceSheet).where(BalanceSheet.period_id == period.period_id)
    )
    cf_row = await session.execute(
        select(CashFlowStatement).where(CashFlowStatement.period_id == period.period_id)
    )

    income = is_row.scalar_one_or_none()
    balance = bs_row.scalar_one_or_none()
    cash = cf_row.scalar_one_or_none()

    return {
        "fiscal_year": period.fiscal_year,
        "fiscal_quarter": period.fiscal_quarter,
        "period_end_date": period.period_end_date.isoformat(),
        "income_statement": _to_plain_dict(income),
        "balance_sheet": _to_plain_dict(balance),
        "cash_flow": _to_plain_dict(cash),
    }


def _to_plain_dict(orm_obj) -> dict:
    """Convert an ORM row into a JSON-friendly dict (numerics → float)."""
    if orm_obj is None:
        return {}
    out: dict = {}
    for column in orm_obj.__table__.columns:
        value = getattr(orm_obj, column.name, None)
        if value is None:
            continue
        try:
            out[column.name] = float(value) if column.type.python_type in (float, int) else value
        except (AttributeError, NotImplementedError, TypeError):
            out[column.name] = value
    return out


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

    # Generate new primer
    llm = get_llm_client()
    financial_data = await _assemble_financial_data(session, entity_id)
    valuation_data: dict = {}  # populated by valuation engines once wired
    ownership_data: dict = {}
    risk_data: dict = {}

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

    financial_data = await _assemble_financial_data(session, entity_id)
    valuation_data: dict = {}

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
