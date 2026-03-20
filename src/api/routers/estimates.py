"""D4 Estimates API endpoints (Spec 6.7)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.estimates import CompanyGuidance, ConsensusEstimate, EstimateSurprise
from src.models.security import Security
from src.models.entity import Entity
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.estimates import (
    CompanyGuidanceResponse,
    ConsensusEstimateResponse,
    EstimateSurpriseResponse,
)

router = APIRouter(tags=["Estimates"])


# ── GET /v1/securities/{id}/estimates/consensus ────────────────────

@router.get("/securities/{security_id}/estimates/consensus", response_model=PaginatedResponse)
async def get_consensus_estimates(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    metric: str | None = Query(None, description="Filter by estimate metric (e.g. EPS, REVENUE)"),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
    period_type: str | None = Query(None, description="Filter by period type"),
):
    """Get consensus analyst estimates for a security."""
    query = select(ConsensusEstimate).where(ConsensusEstimate.security_id == security_id)
    count_query = select(ConsensusEstimate).where(ConsensusEstimate.security_id == security_id)

    if metric:
        query = query.where(ConsensusEstimate.metric == metric.upper())
        count_query = count_query.where(ConsensusEstimate.metric == metric.upper())
    if fiscal_year:
        query = query.where(ConsensusEstimate.fiscal_year == fiscal_year)
        count_query = count_query.where(ConsensusEstimate.fiscal_year == fiscal_year)
    if period_type:
        query = query.where(ConsensusEstimate.period_type == period_type.upper())
        count_query = count_query.where(ConsensusEstimate.period_type == period_type.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(ConsensusEstimate.period_end_date.desc()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    estimates = result.scalars().all()

    return PaginatedResponse(
        data=[ConsensusEstimateResponse.model_validate(e) for e in estimates],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/estimates/surprises ────────────────────

@router.get("/securities/{security_id}/estimates/surprises", response_model=PaginatedResponse)
async def get_estimate_surprises(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    metric: str | None = Query(None, description="Filter by metric"),
):
    """Get earnings surprises for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Security '{security_id}' not found")

    query = select(EstimateSurprise).where(EstimateSurprise.security_id == security_id)
    count_query = select(EstimateSurprise).where(EstimateSurprise.security_id == security_id)

    if metric:
        query = query.where(EstimateSurprise.metric == metric.upper())
        count_query = count_query.where(EstimateSurprise.metric == metric.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(EstimateSurprise.announcement_date.desc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    surprises = result.scalars().all()

    return PaginatedResponse(
        data=[EstimateSurpriseResponse.model_validate(s) for s in surprises],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/guidance ─────────────────────────────────

@router.get("/entities/{entity_id}/guidance", response_model=PaginatedResponse)
async def get_company_guidance(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    metric: str | None = Query(None, description="Filter by metric"),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
):
    """Get company-issued guidance for an entity."""
    query = select(CompanyGuidance).where(CompanyGuidance.entity_id == entity_id)
    count_query = select(CompanyGuidance).where(CompanyGuidance.entity_id == entity_id)

    if metric:
        query = query.where(CompanyGuidance.metric == metric.upper())
        count_query = count_query.where(CompanyGuidance.metric == metric.upper())
    if fiscal_year:
        query = query.where(CompanyGuidance.fiscal_year == fiscal_year)
        count_query = count_query.where(CompanyGuidance.fiscal_year == fiscal_year)

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(CompanyGuidance.guidance_date.desc().nullslast()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    guidance = result.scalars().all()

    return PaginatedResponse(
        data=[CompanyGuidanceResponse.model_validate(g) for g in guidance],
        meta=build_paginated_meta(total_count, pagination),
    )
