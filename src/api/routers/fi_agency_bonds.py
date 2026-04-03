"""Fixed Income - Agency Bonds API endpoints (D11 FI Supplement P8)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.agency_bond import AgencyBond
from src.schemas.agency_bond import AgencyBondResponse, AgencyBondSummary
from src.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(tags=["Fixed Income - Agency Bonds"])


@router.get(
    "/fixed-income/agency-bonds",
    response_model=PaginatedResponse,
)
async def list_agency_bonds(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    agency_type: str | None = Query(None, description="Filter by agency type (FNMA, FHLMC, etc.)"),
    coupon_type: str | None = Query(None, description="Filter by coupon type (FIXED, FLOATING, ZERO)"),
    is_outstanding: bool | None = Query(None, description="Filter by outstanding status"),
    maturity_before: date | None = Query(None, description="Maturity date before"),
    maturity_after: date | None = Query(None, description="Maturity date after"),
):
    """List and filter agency bonds (paginated)."""
    query = select(AgencyBond)
    count_query = select(AgencyBond)

    if agency_type:
        query = query.where(AgencyBond.agency_type == agency_type.upper())
        count_query = count_query.where(AgencyBond.agency_type == agency_type.upper())
    if coupon_type:
        query = query.where(AgencyBond.coupon_type == coupon_type.upper())
        count_query = count_query.where(AgencyBond.coupon_type == coupon_type.upper())
    if is_outstanding is not None:
        query = query.where(AgencyBond.is_outstanding == is_outstanding)
        count_query = count_query.where(AgencyBond.is_outstanding == is_outstanding)
    if maturity_before:
        query = query.where(AgencyBond.maturity_date <= maturity_before)
        count_query = count_query.where(AgencyBond.maturity_date <= maturity_before)
    if maturity_after:
        query = query.where(AgencyBond.maturity_date >= maturity_after)
        count_query = count_query.where(AgencyBond.maturity_date >= maturity_after)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(AgencyBond.maturity_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[AgencyBondSummary.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/agency-bonds/by-agency/{agency_type}",
    response_model=PaginatedResponse,
)
async def bonds_by_agency(
    agency_type: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get agency bonds filtered by agency type."""
    query = select(AgencyBond).where(AgencyBond.agency_type == agency_type.upper())
    count_query = select(AgencyBond).where(AgencyBond.agency_type == agency_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(AgencyBond.maturity_date.desc().nulls_last())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[AgencyBondSummary.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


@router.get(
    "/fixed-income/agency-bonds/{cusip}",
    response_model=AgencyBondResponse,
)
async def get_agency_bond_by_cusip(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single agency bond by CUSIP."""
    query = select(AgencyBond).where(AgencyBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalar_one_or_none()

    if bond is None:
        raise HTTPException(status_code=404, detail=f"Agency bond with CUSIP {cusip} not found")

    return AgencyBondResponse.model_validate(bond)
