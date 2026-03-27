"""Research Primers API endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.company_primer_model import CompanyPrimer, PrimerRefreshLog
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
        .order_by(CompanyPrimer.generated_at.desc().nullslast())
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
    """Trigger a primer refresh for an entity."""
    await _get_entity(session, entity_id)

    refresh = PrimerRefreshLog(
        id=uuid.uuid4(),
        entity_id=entity_id,
        refresh_type="MANUAL",
        trigger_event="API_REQUEST",
        status="PENDING",
        started_at=datetime.now(timezone.utc),
    )
    session.add(refresh)
    await session.flush()

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
