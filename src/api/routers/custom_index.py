"""Custom Index API endpoints (Pillar 2 Supplement – Part 4)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.custom_index import CustomIndex, IndexConstituent, IndexPerformance
from src.schemas.custom_index import (
    CreateIndexRequest,
    CustomIndexResponse,
    IndexConstituentResponse,
    IndexPerformancePointResponse,
    IndexPerformanceResponse,
)

router = APIRouter(tags=["Custom Index"])


@router.post(
    "/analytics/indices",
    response_model=CustomIndexResponse,
    status_code=201,
)
async def create_index(
    body: CreateIndexRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new custom index."""
    index = CustomIndex(
        index_id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        status="ACTIVE",
        weighting_method=body.weighting_method,
        rebalance_frequency=body.rebalance_frequency,
        max_constituents=body.max_constituents,
        inception_date=date.today(),
    )
    session.add(index)
    await session.commit()
    return CustomIndexResponse.model_validate(index)


@router.get(
    "/analytics/indices",
    response_model=list[CustomIndexResponse],
)
async def list_indices(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None, description="Filter by status"),
):
    """List all custom indices."""
    query = select(CustomIndex).order_by(CustomIndex.name)
    if status:
        query = query.where(CustomIndex.status == status.upper())
    result = await session.execute(query)
    rows = result.scalars().all()
    return [CustomIndexResponse.model_validate(r) for r in rows]


@router.get(
    "/analytics/indices/{index_id}",
    response_model=CustomIndexResponse,
)
async def get_index(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a custom index by ID."""
    result = await session.execute(
        select(CustomIndex).where(CustomIndex.index_id == index_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Custom index not found")
    return CustomIndexResponse.model_validate(row)


@router.get(
    "/analytics/indices/{index_id}/constituents",
    response_model=list[IndexConstituentResponse],
)
async def get_index_constituents(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    active_only: bool = Query(True, description="Only active constituents"),
):
    """Get constituents of a custom index."""
    query = select(IndexConstituent).where(IndexConstituent.index_id == index_id)
    if active_only:
        query = query.where(IndexConstituent.is_active == True)  # noqa: E712
    result = await session.execute(query)
    rows = result.scalars().all()
    return [IndexConstituentResponse.model_validate(r) for r in rows]


@router.get(
    "/analytics/indices/{index_id}/performance",
    response_model=IndexPerformanceResponse,
)
async def get_index_performance(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    """Get performance time series for a custom index."""
    query = (
        select(IndexPerformance)
        .where(IndexPerformance.index_id == index_id)
        .order_by(IndexPerformance.perf_date.asc())
    )
    if start:
        query = query.where(IndexPerformance.perf_date >= start)
    if end:
        query = query.where(IndexPerformance.perf_date <= end)

    result = await session.execute(query)
    rows = result.scalars().all()

    points = [
        IndexPerformancePointResponse(
            perf_date=r.perf_date,
            index_level=float(r.index_level) if r.index_level else None,
            daily_return=float(r.daily_return) if r.daily_return else None,
            cumulative_return=float(r.cumulative_return) if r.cumulative_return else None,
        )
        for r in rows
    ]
    return IndexPerformanceResponse(index_id=index_id, points=points)


@router.delete(
    "/analytics/indices/{index_id}",
    status_code=204,
)
async def archive_index(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Archive (soft delete) a custom index."""
    result = await session.execute(
        select(CustomIndex).where(CustomIndex.index_id == index_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Custom index not found")
    row.status = "ARCHIVED"
    await session.commit()
    return None
