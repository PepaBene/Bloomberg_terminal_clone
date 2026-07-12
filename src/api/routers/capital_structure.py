"""Capital Structure API endpoints (Pillar 1 Supplement §2)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.entity import Entity
from src.schemas.capital_structure import (
    CapitalStructureResponse,
    CapitalStructureSummaryResponse,
    DebtTrancheResponse,
)
from src.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(tags=["Capital Structure"])


@router.get(
    "/entities/{entity_id}/capital-structure",
    response_model=CapitalStructureResponse,
)
async def get_capital_structure(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    as_of: date | None = Query(None, description="Point-in-time date"),
):
    """Return the most recent capital structure for an entity."""
    # First verify the entity exists
    ent_result = await session.execute(
        select(Entity.entity_id).where(Entity.entity_id == entity_id)
    )
    if not ent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    query = (
        select(CapitalStructure)
        .where(CapitalStructure.entity_id == entity_id)
        .order_by(CapitalStructure.as_of_date.desc())
    )
    if as_of:
        query = query.where(CapitalStructure.as_of_date <= as_of)
    query = query.limit(1)

    result = await session.execute(query)
    cs = result.scalar_one_or_none()
    if not cs:
        raise HTTPException(status_code=404, detail=f"No capital structure data found for entity '{entity_id}'")
    return CapitalStructureResponse.model_validate(cs)


@router.get(
    "/entities/{entity_id}/capital-structure/tranches",
    response_model=PaginatedResponse,
)
async def list_debt_tranches(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    seniority: str | None = Query(None, description="Filter by seniority type"),
    maturity_before: date | None = Query(None, description="Maturity before date"),
):
    """List individual debt tranches for an entity."""
    query = select(DebtTranche).where(DebtTranche.entity_id == entity_id)
    count_query = select(DebtTranche).where(DebtTranche.entity_id == entity_id)

    if seniority:
        query = query.where(DebtTranche.seniority_type == seniority.upper())
        count_query = count_query.where(DebtTranche.seniority_type == seniority.upper())
    if maturity_before:
        query = query.where(DebtTranche.maturity_date <= maturity_before)
        count_query = count_query.where(DebtTranche.maturity_date <= maturity_before)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(DebtTranche.seniority_rank.asc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    tranches = result.scalars().all()

    return PaginatedResponse(
        data=[DebtTrancheResponse.model_validate(t) for t in tranches],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/capital-structure/history",
    response_model=PaginatedResponse,
)
async def list_capital_structure_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Return capital structure snapshots over time."""
    query = select(CapitalStructure).where(CapitalStructure.entity_id == entity_id)
    count_query = select(CapitalStructure).where(CapitalStructure.entity_id == entity_id)

    if start:
        query = query.where(CapitalStructure.as_of_date >= start)
        count_query = count_query.where(CapitalStructure.as_of_date >= start)
    if end:
        query = query.where(CapitalStructure.as_of_date <= end)
        count_query = count_query.where(CapitalStructure.as_of_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CapitalStructure.as_of_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    records = result.scalars().all()

    return PaginatedResponse(
        data=[CapitalStructureResponse.model_validate(r) for r in records],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/entities/{entity_id}/capital-structure/summary",
    response_model=CapitalStructureSummaryResponse,
)
async def get_capital_structure_summary(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    as_of: date | None = Query(None, description="Point-in-time date"),
):
    """Return aggregate capital structure metrics (no tranche detail)."""
    # First verify the entity exists
    ent_result = await session.execute(
        select(Entity.entity_id).where(Entity.entity_id == entity_id)
    )
    if not ent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    query = (
        select(CapitalStructure)
        .where(CapitalStructure.entity_id == entity_id)
        .order_by(CapitalStructure.as_of_date.desc())
    )
    if as_of:
        query = query.where(CapitalStructure.as_of_date <= as_of)
    query = query.limit(1)

    result = await session.execute(query)
    cs = result.scalar_one_or_none()
    if not cs:
        raise HTTPException(status_code=404, detail=f"No capital structure data found for entity '{entity_id}'")
    return CapitalStructureSummaryResponse.model_validate(cs)
