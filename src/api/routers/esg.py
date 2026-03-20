"""D9 ESG & Sustainability API endpoints (Spec 11.7)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.esg import ESGControversy, ESGMetric, ESGScore
from src.schemas.esg import (
    ESGControversyResponse,
    ESGMetricResponse,
    ESGOverviewResponse,
    ESGScoreResponse,
)

router = APIRouter(tags=["ESG"])


# ── GET /v1/entities/{entity_id}/esg ──────────────────────────────

@router.get("/entities/{entity_id}/esg", response_model=ESGOverviewResponse)
async def get_esg_overview(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    provider: str | None = Query(None, description="Filter scores by provider"),
):
    """Get ESG overview for an entity including scores, metrics, and controversies."""
    # Scores
    scores_query = select(ESGScore).where(ESGScore.entity_id == entity_id)
    if provider:
        scores_query = scores_query.where(ESGScore.provider == provider.upper())
    scores_query = scores_query.order_by(ESGScore.as_of_date.desc())
    scores_result = await session.execute(scores_query)
    scores = scores_result.scalars().all()

    # Metrics
    metrics_result = await session.execute(
        select(ESGMetric)
        .where(ESGMetric.entity_id == entity_id)
        .order_by(ESGMetric.metric_type)
    )
    metrics = metrics_result.scalars().all()

    # Controversies
    controversies_result = await session.execute(
        select(ESGControversy)
        .where(ESGControversy.entity_id == entity_id)
        .order_by(ESGControversy.start_date.desc())
    )
    controversies = controversies_result.scalars().all()

    return ESGOverviewResponse(
        entity_id=entity_id,
        scores=[ESGScoreResponse.model_validate(s) for s in scores],
        metrics=[ESGMetricResponse.model_validate(m) for m in metrics],
        controversies=[ESGControversyResponse.model_validate(c) for c in controversies],
    )


# ── GET /v1/entities/{entity_id}/esg/scores ───────────────────────

@router.get("/entities/{entity_id}/esg/scores", response_model=list[ESGScoreResponse])
async def get_esg_scores(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    provider: str | None = Query(None, description="Filter by ESG provider"),
):
    """Get ESG scores for an entity."""
    query = select(ESGScore).where(ESGScore.entity_id == entity_id)
    if provider:
        query = query.where(ESGScore.provider == provider.upper())
    query = query.order_by(ESGScore.as_of_date.desc())

    result = await session.execute(query)
    scores = result.scalars().all()
    return [ESGScoreResponse.model_validate(s) for s in scores]


# ── GET /v1/entities/{entity_id}/esg/metrics ──────────────────────

@router.get("/entities/{entity_id}/esg/metrics", response_model=list[ESGMetricResponse])
async def get_esg_metrics(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    category: str | None = Query(None, description="Filter by ESG category (ENVIRONMENTAL, SOCIAL, GOVERNANCE)"),
):
    """Get ESG metrics for an entity."""
    query = select(ESGMetric).where(ESGMetric.entity_id == entity_id)
    if category:
        query = query.where(ESGMetric.metric_category == category.upper())
    query = query.order_by(ESGMetric.metric_type)

    result = await session.execute(query)
    metrics = result.scalars().all()
    return [ESGMetricResponse.model_validate(m) for m in metrics]


# ── GET /v1/entities/{entity_id}/esg/controversies ────────────────

@router.get("/entities/{entity_id}/esg/controversies", response_model=list[ESGControversyResponse])
async def get_esg_controversies(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None, description="Filter by status (ONGOING, RESOLVED, ESCALATING)"),
):
    """Get ESG controversies for an entity."""
    query = select(ESGControversy).where(ESGControversy.entity_id == entity_id)
    if status:
        query = query.where(ESGControversy.status == status.upper())
    query = query.order_by(ESGControversy.start_date.desc())

    result = await session.execute(query)
    controversies = result.scalars().all()
    return [ESGControversyResponse.model_validate(c) for c in controversies]
