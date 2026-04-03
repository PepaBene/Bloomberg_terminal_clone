"""Fixed Income - Bond Issuances API endpoints (D11 FI Supplement P7)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.issuance_analytics import (
    aggregate_issuance_volume,
    compute_league_table,
)
from src.models.bond_issuance import BondIssuance
from src.schemas.bond_issuance import (
    BondIssuanceResponse,
    IssuanceVolumeResponse,
    LeagueTableEntry,
)
from src.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(tags=["Fixed Income - Bond Issuances"])


@router.get(
    "/fixed-income/issuances",
    response_model=PaginatedResponse,
)
async def list_issuances(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    seniority: str | None = Query(None, description="Filter by seniority"),
    currency: str | None = Query(None, description="Filter by currency"),
    date_from: date | None = Query(None, description="Pricing date from"),
    date_to: date | None = Query(None, description="Pricing date to"),
):
    """List and filter bond issuances (paginated)."""
    query = select(BondIssuance)
    count_query = select(BondIssuance)

    if seniority:
        query = query.where(BondIssuance.seniority == seniority.upper())
        count_query = count_query.where(BondIssuance.seniority == seniority.upper())
    if currency:
        query = query.where(BondIssuance.currency == currency.upper())
        count_query = count_query.where(BondIssuance.currency == currency.upper())
    if date_from:
        query = query.where(BondIssuance.pricing_date >= date_from)
        count_query = count_query.where(BondIssuance.pricing_date >= date_from)
    if date_to:
        query = query.where(BondIssuance.pricing_date <= date_to)
        count_query = count_query.where(BondIssuance.pricing_date <= date_to)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondIssuance.pricing_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondIssuanceResponse.model_validate(i) for i in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/issuances/volume",
    response_model=list[IssuanceVolumeResponse],
)
async def issuance_volume(
    session: AsyncSession = Depends(get_session),
    period: str = Query("monthly", description="Aggregation period: monthly, quarterly, yearly"),
):
    """Aggregate issuance volume statistics by period."""
    query = select(BondIssuance).where(BondIssuance.pricing_date.isnot(None))
    result = await session.execute(query)
    issuances = result.scalars().all()

    iss_dicts = [
        {
            "pricing_date": i.pricing_date,
            "issued_size_mm": float(i.issued_size_mm) if i.issued_size_mm is not None else None,
        }
        for i in issuances
    ]

    volume_data = aggregate_issuance_volume(iss_dicts, period=period)
    if not volume_data:
        return []
    return [IssuanceVolumeResponse(**v) for v in volume_data]


@router.get(
    "/fixed-income/issuances/league-tables",
    response_model=list[LeagueTableEntry],
)
async def league_tables(
    session: AsyncSession = Depends(get_session),
):
    """Bookrunner league table ranked by deal volume."""
    query = select(BondIssuance).where(BondIssuance.lead_left_bookrunner.isnot(None))
    result = await session.execute(query)
    issuances = result.scalars().all()

    iss_dicts = [
        {
            "lead_left_bookrunner": i.lead_left_bookrunner,
            "issued_size_mm": float(i.issued_size_mm) if i.issued_size_mm is not None else None,
        }
        for i in issuances
    ]

    table = compute_league_table(iss_dicts)
    if not table:
        return []
    return [LeagueTableEntry(**entry) for entry in table]


@router.get(
    "/fixed-income/issuances/by-issuer/{entity_id}",
    response_model=PaginatedResponse,
)
async def issuances_by_issuer(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get all bond issuances for a specific issuer entity."""
    query = select(BondIssuance).where(BondIssuance.issuer_entity_id == entity_id)
    count_query = select(BondIssuance).where(BondIssuance.issuer_entity_id == entity_id)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondIssuance.pricing_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondIssuanceResponse.model_validate(i) for i in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/issuances/{issuance_id}",
    response_model=BondIssuanceResponse,
)
async def get_issuance(
    issuance_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single bond issuance by ID."""
    query = select(BondIssuance).where(BondIssuance.issuance_id == issuance_id)
    result = await session.execute(query)
    issuance = result.scalar_one_or_none()

    if issuance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Bond issuance with ID {issuance_id} not found",
        )

    return BondIssuanceResponse.model_validate(issuance)
