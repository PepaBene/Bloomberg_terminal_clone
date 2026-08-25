"""Consensus Estimates API endpoints (Spec 6.3).

Exposes ``consensus_estimates`` and ``estimate_surprises`` -- both ingested
by scripts.ingest_consensus_estimates / EarningsSurprisesConnector but never
previously reachable through any API route.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.estimates import ConsensusEstimate, EstimateSurprise
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.estimates import ConsensusEstimateResponse, EstimateSurpriseResponse

router = APIRouter(tags=["Consensus Estimates"])


@router.get(
    "/securities/{security_id}/consensus-estimates",
    response_model=PaginatedResponse,
)
async def list_consensus_estimates(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    metric: str | None = Query(None, description="Filter by metric (EPS, REVENUE, ...)"),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
):
    """List consensus analyst estimates for a security, most recent first."""
    query = select(ConsensusEstimate).where(ConsensusEstimate.security_id == security_id)
    count_query = select(ConsensusEstimate).where(ConsensusEstimate.security_id == security_id)

    if metric:
        query = query.where(ConsensusEstimate.metric == metric)
        count_query = count_query.where(ConsensusEstimate.metric == metric)
    if fiscal_year:
        query = query.where(ConsensusEstimate.fiscal_year == fiscal_year)
        count_query = count_query.where(ConsensusEstimate.fiscal_year == fiscal_year)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(
            ConsensusEstimate.as_of_date.desc(),
            ConsensusEstimate.period_end_date.desc(),
        )
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    estimates = result.scalars().all()

    return PaginatedResponse(
        data=[ConsensusEstimateResponse.model_validate(e) for e in estimates],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/securities/{security_id}/estimate-surprises",
    response_model=PaginatedResponse,
)
async def list_estimate_surprises(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    metric: str | None = Query(None, description="Filter by metric (EPS, REVENUE, ...)"),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
):
    """List actual-vs-consensus surprises for a security, most recent first."""
    query = select(EstimateSurprise).where(EstimateSurprise.security_id == security_id)
    count_query = select(EstimateSurprise).where(EstimateSurprise.security_id == security_id)

    if metric:
        query = query.where(EstimateSurprise.metric == metric)
        count_query = count_query.where(EstimateSurprise.metric == metric)
    if fiscal_year:
        query = query.where(EstimateSurprise.fiscal_year == fiscal_year)
        count_query = count_query.where(EstimateSurprise.fiscal_year == fiscal_year)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(
            EstimateSurprise.fiscal_year.desc(),
            EstimateSurprise.fiscal_quarter.desc(),
        )
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    surprises = result.scalars().all()

    return PaginatedResponse(
        data=[EstimateSurpriseResponse.model_validate(s) for s in surprises],
        meta=build_paginated_meta(total_count, pagination),
    )
