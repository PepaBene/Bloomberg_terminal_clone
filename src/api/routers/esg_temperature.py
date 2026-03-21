"""ESG Temperature Scoring API endpoints (Pillar 1 Supplement §15)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.esg_temperature import ESGTemperatureScore
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.esg_temperature import ESGTemperatureResponse

router = APIRouter(tags=["ESG Temperature"])


@router.get(
    "/entities/{entity_id}/esg-temperature",
    response_model=PaginatedResponse,
)
async def list_esg_temperature(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    alignment: str | None = Query(None, description="Filter by alignment bucket"),
):
    """List ESG implied-temperature scores for an entity."""
    base = select(ESGTemperatureScore).where(
        ESGTemperatureScore.entity_id == entity_id
    )
    count_q = base

    if alignment:
        base = base.where(ESGTemperatureScore.alignment == alignment.upper())
        count_q = count_q.where(ESGTemperatureScore.alignment == alignment.upper())

    total = (await session.execute(
        select(sa_func.count()).select_from(count_q.subquery())
    )).scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    rows = (await session.execute(
        base.order_by(ESGTemperatureScore.as_of_date.desc())
        .offset(offset).limit(pagination.page_size)
    )).scalars().all()

    return PaginatedResponse(
        data=[ESGTemperatureResponse.model_validate(r) for r in rows],
        meta=build_paginated_meta(total, pagination),
    )
