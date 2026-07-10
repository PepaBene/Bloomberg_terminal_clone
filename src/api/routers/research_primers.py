"""Research Primers API endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.deps import get_session
from src.engines import company_primer_engine
from src.models.company_primer_model import CompanyPrimer, PrimerRefreshLog
from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent
from src.models.fundamentals import FinancialPeriod, SegmentData  # noqa: F401 — relationships load statements
from src.models.news_article import ArticleEntityLink, NewsArticle
from src.models.security import EODPrice, EquityDetails, Security
from src.schemas.company_primer_schema import (
    CompanyPrimerResponse,
    PrimerCompletenessResponse,
    PrimerListResponse,
    PrimerRefreshResponse,
)

router = APIRouter(tags=["Research - Company Primers"])


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _float(val):
    return float(val) if val is not None else None


async def _assemble_primer_inputs(session: AsyncSession, entity: Entity) -> tuple[dict, dict, list[dict]]:
    """Gather the entity_data / filings / news dicts that
    company_primer_engine.build_company_primer() consumes, from real
    Pillar 1/2 data. Sections with no ingested source stay empty rather than
    being fabricated — the engine and its completeness score handle that.
    """
    entity_id = entity.entity_id

    # Two most recent periods for growth; latest for the financial snapshot.
    periods = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(2)
        )
    ).scalars().all()

    financial_data: dict = {}
    entity_data: dict = {"name": entity.legal_name}
    last_filing_date = None
    if periods:
        latest = periods[0]
        last_filing_date = latest.period_end_date
        inc = latest.income_statement
        bs = latest.balance_sheet
        cf = latest.cash_flow
        rev = float(inc.total_revenue) if inc and inc.total_revenue is not None else None
        if inc:
            financial_data["revenue_ttm"] = rev or 0.0
            if inc.cost_of_revenue is not None:
                financial_data["cost_of_revenue"] = float(inc.cost_of_revenue)
            if inc.operating_income is not None:
                financial_data["operating_income"] = float(inc.operating_income)
            if inc.net_income is not None:
                financial_data["net_income"] = float(inc.net_income)
            if inc.ebitda is not None:
                financial_data["ebitda"] = float(inc.ebitda)
            if rev and inc.operating_income is not None:
                entity_data["operating_margin"] = round(float(inc.operating_income) / rev * 100, 2)
                entity_data["revenue"] = rev
        if bs:
            if bs.total_debt is not None:
                financial_data["total_debt"] = float(bs.total_debt)
            if bs.cash_and_equivalents is not None:
                financial_data["cash"] = float(bs.cash_and_equivalents)
        if cf and cf.free_cash_flow is not None:
            financial_data["free_cash_flow"] = float(cf.free_cash_flow)

        if len(periods) > 1 and periods[1].income_statement and periods[1].income_statement.total_revenue and rev:
            prev_rev = float(periods[1].income_statement.total_revenue)
            if prev_rev:
                entity_data["revenue_growth_pct"] = round((rev - prev_rev) / prev_rev * 100, 2)

    # Market cap = primary equity shares × latest close.
    sec_row = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        )
    ).all()
    if sec_row:
        sec_row.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
        security_id = sec_row[0][0]
        shares = (
            await session.execute(
                select(EquityDetails.shares_outstanding).where(EquityDetails.security_id == security_id)
            )
        ).scalar_one_or_none()
        close = (
            await session.execute(
                select(EODPrice.close)
                .where(EODPrice.security_id == security_id, EODPrice.close.isnot(None))
                .order_by(EODPrice.price_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if shares is not None and close is not None:
            entity_data["market_cap"] = float(shares) * float(close)

    # Business (product) segments — segment ingestion is BUSINESS-typed.
    seg_rows = (
        await session.execute(
            select(SegmentData.segment_name, SegmentData.segment_type)
            .where(SegmentData.entity_id == entity_id)
            .limit(50)
        )
    ).all()
    product_segments = sorted({name for name, styp in seg_rows if styp == "BUSINESS" and name})
    geographic = sorted({name for name, styp in seg_rows if styp == "GEOGRAPHIC" and name})

    # 8-K events → strategic-initiative candidates (now that edgar_8k writes EightKEvent).
    eight_k_rows = (
        await session.execute(
            select(EightKEvent)
            .where(EightKEvent.entity_id == entity_id)
            .order_by(EightKEvent.filing_date.desc())
            .limit(20)
        )
    ).scalars().all()
    eight_k_events = [
        {
            "title": ev.item_description or f"8-K Item {ev.item_number}",
            "description": ev.item_description or "",
            "date": ev.filing_date.isoformat() if ev.filing_date else "",
            "event_type": "strategic" if ev.priority <= 2 else "other",
        }
        for ev in eight_k_rows
    ]

    filings: dict = {
        "financial_data": financial_data,
        "segment_data": {"geographic": geographic, "product_segments": product_segments},
        "eight_k_events": eight_k_events,
        "risks": [],
        "catalyst_events": [],
        "earnings_dates": [],
    }

    # Recent news linked to the entity (Finnhub-ingested).
    news_rows = (
        await session.execute(
            select(NewsArticle)
            .join(ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id)
            .where(ArticleEntityLink.entity_id == entity_id)
            .order_by(NewsArticle.publish_date.desc())
            .limit(10)
        )
    ).scalars().all()
    news = [
        {
            "headline": n.title,
            "date": n.publish_date.isoformat() if n.publish_date else "",
            "source": n.source_name,
        }
        for n in news_rows
    ]

    entity_data["_last_filing_date"] = last_filing_date
    return entity_data, filings, news


async def _generate_primer(session: AsyncSession, entity: Entity) -> CompanyPrimer:
    """Run company_primer_engine over real data, persist a new versioned
    research_primers row, and return it. Optionally adds an LLM executive
    summary when configured."""
    entity_data, filings, news = await _assemble_primer_inputs(session, entity)
    last_filing_date = entity_data.pop("_last_filing_date", None)

    result = company_primer_engine.build_company_primer(
        entity_data=entity_data,
        filings=filings,
        transcripts=None,
        news=news,
        peers=[],
    )

    llm = get_llm_client()
    executive_summary = None
    if llm.enabled:
        executive_summary = await llm.generate(
            system_prompt=(
                "You are a senior equity research analyst. Write a concise (3-5 "
                "sentence) executive summary for a company research primer, "
                "grounded strictly in the provided structured data."
            ),
            user_prompt=(
                f"Company: {result.entity_name}\n"
                f"Financial health: {filings['financial_data']}\n"
                f"Market position: {result.competitive.market_position}\n"
                f"Top risks: {[r.description for r in result.risks[:3]]}"
            ),
        )

    max_version = (
        await session.execute(
            select(func.max(CompanyPrimer.primer_version)).where(CompanyPrimer.entity_id == entity.entity_id)
        )
    ).scalar() or 0

    fh = result.financial_health
    primer = CompanyPrimer(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        primer_version=max_version + 1,
        executive_summary=executive_summary,
        business_model={
            "revenue_streams": result.business_model.revenue_streams,
            "customer_segments": result.business_model.customer_segments,
            "geographic_exposure": result.business_model.geographic_exposure,
            "key_partnerships": result.business_model.key_partnerships,
        },
        competitive_landscape={
            "direct_competitors": result.competitive.direct_competitors,
            "competitive_advantages": result.competitive.competitive_advantages,
            "market_position": result.competitive.market_position,
        },
        financial_health={
            "revenue_ttm": fh.revenue_ttm,
            "gross_margin": fh.gross_margin,
            "operating_margin": fh.operating_margin,
            "net_margin": fh.net_margin,
            "net_debt_to_ebitda": fh.net_debt_to_ebitda,
            "fcf_margin": fh.fcf_margin,
        },
        strategic_initiatives={
            "initiatives": [
                {"name": i.name, "description": i.description, "timeline": i.timeline,
                 "potential_impact": i.potential_impact}
                for i in result.initiatives
            ]
        },
        risk_factors={
            "risks": [
                {"category": r.category, "description": r.description, "severity": r.severity}
                for r in result.risks
            ]
        },
        recent_catalysts={
            "catalysts": [
                {"date": c.date, "event": c.event,
                 "strategic_significance": c.strategic_significance}
                for c in result.catalysts
            ]
        },
        data_completeness_score=result.data_completeness,
        last_filing_date=last_filing_date,
        ai_enabled=executive_summary is not None,
        prompt_template_used="company_primer_engine.v1",
    )
    session.add(primer)
    await session.commit()
    await session.refresh(primer)
    return primer


def _primer_response(row: CompanyPrimer) -> CompanyPrimerResponse:
    return CompanyPrimerResponse(
        id=row.id,
        entity_id=row.entity_id,
        primer_version=row.primer_version,
        generated_at=row.generated_at,
        executive_summary=row.executive_summary,
        business_model=row.business_model,
        competitive_landscape=row.competitive_landscape,
        financial_health=row.financial_health,
        strategic_initiatives=row.strategic_initiatives,
        risk_factors=row.risk_factors,
        analyst_consensus=row.analyst_consensus,
        recent_catalysts=row.recent_catalysts,
        data_completeness_score=_float(row.data_completeness_score),
        last_filing_date=row.last_filing_date,
        last_earnings_call_date=row.last_earnings_call_date,
        ai_enabled=row.ai_enabled,
        prompt_template_used=row.prompt_template_used,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/primers/recent",
    response_model=list[PrimerListResponse],
)
async def get_recent_primers(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Recently generated primers across all entities."""
    result = await session.execute(
        select(CompanyPrimer)
        .order_by(CompanyPrimer.generated_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        PrimerListResponse(
            entity_id=row.entity_id,
            primer_version=row.primer_version,
            generated_at=row.generated_at,
            executive_summary=row.executive_summary,
            data_completeness_score=_float(row.data_completeness_score),
        )
        for row in rows
    ]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/primers/{entity_id}",
    response_model=CompanyPrimerResponse,
)
async def get_latest_primer(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest company primer for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return _primer_response(row)


@router.get(
    "/research/primers/{entity_id}/history",
    response_model=list[PrimerListResponse],
)
async def get_primer_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get primer version history for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
    )
    rows = result.scalars().all()

    return [
        PrimerListResponse(
            entity_id=row.entity_id,
            primer_version=row.primer_version,
            generated_at=row.generated_at,
            executive_summary=row.executive_summary,
            data_completeness_score=_float(row.data_completeness_score),
        )
        for row in rows
    ]


@router.post(
    "/research/primers/{entity_id}/refresh",
    response_model=PrimerRefreshResponse,
)
async def trigger_primer_refresh(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a primer refresh for an entity.

    Actually generates and persists a new research_primers row via
    company_primer_engine over real Pillar 1/2 data, then advances the
    refresh log to DONE — previously this only inserted a PENDING log row
    that nothing ever advanced, and no primer was ever produced.
    """
    entity = await _get_entity(session, entity_id)

    refresh = PrimerRefreshLog(
        id=uuid.uuid4(),
        entity_id=entity_id,
        refresh_type="MANUAL",
        trigger_event="API_REQUEST",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    session.add(refresh)
    await session.commit()

    try:
        await _generate_primer(session, entity)
        refresh.status = "DONE"
    except Exception:
        refresh.status = "FAILED"
        refresh.completed_at = datetime.now(timezone.utc)
        await session.commit()
        raise
    refresh.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(refresh)

    return PrimerRefreshResponse(
        id=refresh.id,
        entity_id=refresh.entity_id,
        refresh_type=refresh.refresh_type,
        trigger_event=refresh.trigger_event,
        status=refresh.status,
        started_at=refresh.started_at,
        completed_at=refresh.completed_at,
        created_at=refresh.created_at,
    )


@router.get(
    "/research/primers/{entity_id}/completeness",
    response_model=PrimerCompletenessResponse,
)
async def get_primer_completeness(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get data completeness score for the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return PrimerCompletenessResponse(
        entity_id=row.entity_id,
        data_completeness_score=_float(row.data_completeness_score),
        last_filing_date=row.last_filing_date,
        last_earnings_call_date=row.last_earnings_call_date,
        ai_enabled=row.ai_enabled,
    )


@router.get(
    "/research/primers/{entity_id}/risks",
    response_model=dict,
)
async def get_primer_risks(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get risk factors extract from the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "risk_factors": row.risk_factors,
    }


@router.get(
    "/research/primers/{entity_id}/catalysts",
    response_model=dict,
)
async def get_primer_catalysts(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get catalyst calendar from the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "recent_catalysts": row.recent_catalysts,
    }


@router.get(
    "/research/primers/{entity_id}/financials",
    response_model=dict,
)
async def get_primer_financials(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get financial health snapshot from the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "financial_health": row.financial_health,
    }


@router.get(
    "/research/primers/{entity_id}/competitive",
    response_model=dict,
)
async def get_primer_competitive(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get competitive landscape from the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "competitive_landscape": row.competitive_landscape,
    }


@router.get(
    "/research/primers/{entity_id}/strategic",
    response_model=dict,
)
async def get_primer_strategic(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get strategic initiatives from the latest primer."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(CompanyPrimer)
        .where(CompanyPrimer.entity_id == entity_id)
        .order_by(CompanyPrimer.primer_version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No primer found for this entity")

    return {
        "entity_id": str(row.entity_id),
        "strategic_initiatives": row.strategic_initiatives,
    }
