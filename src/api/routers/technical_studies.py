"""Technical Studies API endpoints (Pillar 1 Supplement §13)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.technical_studies import TechnicalStudyValue
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.technical_studies import TechnicalStudyResponse

router = APIRouter(tags=["Technical Studies"])


@router.get(
    "/securities/{security_id}/technicals",
    response_model=PaginatedResponse,
)
async def list_technicals(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    study_date: date | None = Query(None, description="Exact date"),
    indicator: str | None = Query(None, description="Filter by indicator name"),
    category: str | None = Query(None, description="Filter by category"),
):
    """List technical indicator values for a security."""
    base = select(TechnicalStudyValue).where(
        TechnicalStudyValue.security_id == security_id
    )
    count_q = base

    if study_date:
        base = base.where(TechnicalStudyValue.study_date == study_date)
        count_q = count_q.where(TechnicalStudyValue.study_date == study_date)
    if indicator:
        base = base.where(TechnicalStudyValue.indicator == indicator.upper())
        count_q = count_q.where(TechnicalStudyValue.indicator == indicator.upper())
    if category:
        base = base.where(TechnicalStudyValue.category == category.upper())
        count_q = count_q.where(TechnicalStudyValue.category == category.upper())

    total = (await session.execute(
        select(sa_func.count()).select_from(count_q.subquery())
    )).scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    rows = (await session.execute(
        base.order_by(TechnicalStudyValue.study_date.desc(), TechnicalStudyValue.indicator)
        .offset(offset).limit(pagination.page_size)
    )).scalars().all()

    return PaginatedResponse(
        data=[TechnicalStudyResponse.model_validate(r) for r in rows],
        meta=build_paginated_meta(total, pagination),
    )


@router.get(
    "/securities/{security_id}/technicals/{indicator}",
    response_model=PaginatedResponse,
)
async def get_indicator_history(
    security_id: uuid.UUID,
    indicator: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    """Return time-series for a specific indicator on a security."""
    base = select(TechnicalStudyValue).where(
        TechnicalStudyValue.security_id == security_id,
        TechnicalStudyValue.indicator == indicator.upper(),
    )
    count_q = base

    if start:
        base = base.where(TechnicalStudyValue.study_date >= start)
        count_q = count_q.where(TechnicalStudyValue.study_date >= start)
    if end:
        base = base.where(TechnicalStudyValue.study_date <= end)
        count_q = count_q.where(TechnicalStudyValue.study_date <= end)

    total = (await session.execute(
        select(sa_func.count()).select_from(count_q.subquery())
    )).scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    rows = (await session.execute(
        base.order_by(TechnicalStudyValue.study_date.desc())
        .offset(offset).limit(pagination.page_size)
    )).scalars().all()

    return PaginatedResponse(
        data=[TechnicalStudyResponse.model_validate(r) for r in rows],
        meta=build_paginated_meta(total, pagination),
    )
