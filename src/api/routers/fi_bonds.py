"""Fixed Income - Corporate Bonds API endpoints (D11 FI Supplement P4)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.engines.bond_analytics import (
    compute_convexity,
    compute_g_spread,
    compute_macaulay_duration,
    compute_modified_duration,
    compute_ytm,
    compute_ytw,
)
from src.models.corporate_bond import (
    BondCallSchedule,
    BondEODPrice,
    BondTrade,
    CorporateBond,
)
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.corporate_bond import (
    BondAnalyticsResponse,
    BondCallScheduleResponse,
    BondEODPriceResponse,
    BondScreenRequest,
    BondTradeResponse,
    CorporateBondResponse,
)

router = APIRouter(tags=["Fixed Income - Corporate Bonds"])


# ── 1. GET /fixed-income/bonds — list/filter (paginated) ──────────────


@router.get(
    "/fixed-income/bonds",
    response_model=PaginatedResponse,
)
async def list_bonds(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    seniority: str | None = Query(None, description="Filter by seniority"),
    coupon_type: str | None = Query(None, description="Filter by coupon type"),
    currency: str | None = Query(None, description="Filter by currency"),
    status: str | None = Query(None, description="Filter by status"),
    is_callable: bool | None = Query(None, description="Filter by callable"),
    is_investment_grade: bool | None = Query(None, description="Filter by investment grade"),
    maturity_before: date | None = Query(None, description="Maturity before date"),
    maturity_after: date | None = Query(None, description="Maturity after date"),
):
    """List and filter corporate bonds (paginated)."""
    query = select(CorporateBond)
    count_query = select(CorporateBond)

    filters = []
    if seniority:
        filters.append(CorporateBond.seniority == seniority)
    if coupon_type:
        filters.append(CorporateBond.coupon_type == coupon_type)
    if currency:
        filters.append(CorporateBond.currency == currency)
    if status:
        filters.append(CorporateBond.status == status)
    if is_callable is not None:
        filters.append(CorporateBond.is_callable == is_callable)  # noqa: E712
    if is_investment_grade is not None:
        filters.append(CorporateBond.is_investment_grade == is_investment_grade)  # noqa: E712
    if maturity_before:
        filters.append(CorporateBond.maturity_date <= maturity_before)
    if maturity_after:
        filters.append(CorporateBond.maturity_date >= maturity_after)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CorporateBond.maturity_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().unique().all()

    return PaginatedResponse(
        data=[CorporateBondResponse.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 2. GET /fixed-income/bonds/search — full-text search ──────────────


@router.get(
    "/fixed-income/bonds/search",
    response_model=PaginatedResponse,
)
async def search_bonds(
    q: str = Query(..., description="Search query"),
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Full-text search on bond name, issuer name, and CUSIP."""
    pattern = f"%{q}%"
    query = select(CorporateBond).where(
        (CorporateBond.name.ilike(pattern))
        | (CorporateBond.issuer_name.ilike(pattern))
        | (CorporateBond.cusip.ilike(pattern))
    )
    count_query = select(CorporateBond).where(
        (CorporateBond.name.ilike(pattern))
        | (CorporateBond.issuer_name.ilike(pattern))
        | (CorporateBond.cusip.ilike(pattern))
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    items = result.scalars().unique().all()

    return PaginatedResponse(
        data=[CorporateBondResponse.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 3. POST /fixed-income/screen/bonds — advanced screening ───────────


@router.post(
    "/fixed-income/screen/bonds",
    response_model=PaginatedResponse,
)
async def screen_bonds(
    body: BondScreenRequest,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Advanced bond screening with multiple criteria."""
    query = select(CorporateBond)
    count_query = select(CorporateBond)

    filters = []
    if body.seniority:
        filters.append(CorporateBond.seniority == body.seniority)
    if body.coupon_type:
        filters.append(CorporateBond.coupon_type == body.coupon_type)
    if body.min_coupon is not None:
        filters.append(CorporateBond.coupon_rate >= body.min_coupon)
    if body.max_coupon is not None:
        filters.append(CorporateBond.coupon_rate <= body.max_coupon)
    if body.min_maturity:
        filters.append(CorporateBond.maturity_date >= body.min_maturity)
    if body.max_maturity:
        filters.append(CorporateBond.maturity_date <= body.max_maturity)
    if body.currency:
        filters.append(CorporateBond.currency == body.currency)
    if body.is_callable is not None:
        filters.append(CorporateBond.is_callable == body.is_callable)  # noqa: E712
    if body.is_convertible is not None:
        filters.append(CorporateBond.is_convertible == body.is_convertible)  # noqa: E712
    if body.is_investment_grade is not None:
        filters.append(CorporateBond.is_investment_grade == body.is_investment_grade)  # noqa: E712
    if body.status:
        filters.append(CorporateBond.status == body.status)
    if body.min_outstanding is not None:
        filters.append(CorporateBond.outstanding_amount >= body.min_outstanding)
    if body.max_outstanding is not None:
        filters.append(CorporateBond.outstanding_amount <= body.max_outstanding)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    items = result.scalars().unique().all()

    return PaginatedResponse(
        data=[CorporateBondResponse.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 4. POST /fixed-income/screen/issuers — screen by credit quality ───


@router.post(
    "/fixed-income/screen/issuers",
    response_model=PaginatedResponse,
)
async def screen_issuers(
    body: BondScreenRequest,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Screen issuers by credit quality (investment grade, rating filters)."""
    query = select(CorporateBond)
    count_query = select(CorporateBond)

    filters = []
    if body.is_investment_grade is not None:
        filters.append(CorporateBond.is_investment_grade == body.is_investment_grade)  # noqa: E712
    if body.seniority:
        filters.append(CorporateBond.seniority == body.seniority)
    if body.currency:
        filters.append(CorporateBond.currency == body.currency)
    if body.status:
        filters.append(CorporateBond.status == body.status)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    # Group by issuer — return distinct issuer bonds
    query = query.order_by(CorporateBond.issuer_entity_id)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    items = result.scalars().unique().all()

    return PaginatedResponse(
        data=[CorporateBondResponse.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 5. GET /fixed-income/issuers/{entity_id}/bonds ────────────────────


@router.get(
    "/fixed-income/issuers/{entity_id}/bonds",
    response_model=PaginatedResponse,
)
async def bonds_by_issuer(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get all bonds for a given issuer entity."""
    query = select(CorporateBond).where(
        CorporateBond.issuer_entity_id == entity_id
    )
    count_query = select(CorporateBond).where(
        CorporateBond.issuer_entity_id == entity_id
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CorporateBond.maturity_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().unique().all()

    return PaginatedResponse(
        data=[CorporateBondResponse.model_validate(b) for b in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 6. GET /fixed-income/issuers/{entity_id}/bond-prices ──────────────


@router.get(
    "/fixed-income/issuers/{entity_id}/bond-prices",
    response_model=PaginatedResponse,
)
async def bond_prices_by_issuer(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get latest EOD prices for all bonds issued by an entity."""
    # Get all bond IDs for this issuer
    bond_q = select(CorporateBond.bond_id).where(
        CorporateBond.issuer_entity_id == entity_id
    )
    bond_result = await session.execute(bond_q)
    bond_ids = [row[0] for row in bond_result.all()]

    if not bond_ids:
        return PaginatedResponse(
            data=[],
            meta=build_paginated_meta(0, pagination),
        )

    query = select(BondEODPrice).where(BondEODPrice.bond_id.in_(bond_ids))
    count_query = select(BondEODPrice).where(BondEODPrice.bond_id.in_(bond_ids))

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondEODPrice.price_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondEODPriceResponse.model_validate(p) for p in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 7. GET /fixed-income/bonds/{cusip} — detail ───────────────────────


@router.get(
    "/fixed-income/bonds/{cusip}",
    response_model=CorporateBondResponse,
)
async def get_bond_by_cusip(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single corporate bond by CUSIP."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    return CorporateBondResponse.model_validate(bond)


# ── 8. GET /fixed-income/bonds/{cusip}/call-schedule ───────────────────


@router.get(
    "/fixed-income/bonds/{cusip}/call-schedule",
    response_model=list[BondCallScheduleResponse],
)
async def get_call_schedule(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the call schedule for a bond."""
    bond_q = select(CorporateBond).where(CorporateBond.cusip == cusip)
    bond_result = await session.execute(bond_q)
    bond = bond_result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    query = (
        select(BondCallSchedule)
        .where(BondCallSchedule.bond_id == bond.bond_id)
        .order_by(BondCallSchedule.call_date.asc())
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return [BondCallScheduleResponse.model_validate(c) for c in items]


# ── 9. GET /fixed-income/bonds/{cusip}/price — latest EOD price ────────


@router.get(
    "/fixed-income/bonds/{cusip}/price",
    response_model=BondEODPriceResponse,
)
async def get_latest_price(
    cusip: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest EOD price for a bond."""
    bond_q = select(CorporateBond).where(CorporateBond.cusip == cusip)
    bond_result = await session.execute(bond_q)
    bond = bond_result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    query = (
        select(BondEODPrice)
        .where(BondEODPrice.bond_id == bond.bond_id)
        .order_by(BondEODPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(query)
    price = result.scalar_one_or_none()

    if price is None:
        raise HTTPException(
            status_code=404, detail=f"No price data for bond {cusip}"
        )

    return BondEODPriceResponse.model_validate(price)


# ── 10. GET /fixed-income/bonds/{cusip}/price-history ──────────────────


@router.get(
    "/fixed-income/bonds/{cusip}/price-history",
    response_model=PaginatedResponse,
)
async def get_price_history(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get historical EOD prices for a bond."""
    bond_q = select(CorporateBond).where(CorporateBond.cusip == cusip)
    bond_result = await session.execute(bond_q)
    bond = bond_result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    query = select(BondEODPrice).where(BondEODPrice.bond_id == bond.bond_id)
    count_query = select(BondEODPrice).where(BondEODPrice.bond_id == bond.bond_id)

    if start:
        query = query.where(BondEODPrice.price_date >= start)
        count_query = count_query.where(BondEODPrice.price_date >= start)
    if end:
        query = query.where(BondEODPrice.price_date <= end)
        count_query = count_query.where(BondEODPrice.price_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondEODPrice.price_date.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondEODPriceResponse.model_validate(p) for p in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 11. GET /fixed-income/bonds/{cusip}/trades — TRACE trades ─────────


@router.get(
    "/fixed-income/bonds/{cusip}/trades",
    response_model=PaginatedResponse,
)
async def get_trades(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get TRACE trades for a bond."""
    bond_q = select(CorporateBond).where(CorporateBond.cusip == cusip)
    bond_result = await session.execute(bond_q)
    bond = bond_result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    query = select(BondTrade).where(BondTrade.bond_id == bond.bond_id)
    count_query = select(BondTrade).where(BondTrade.bond_id == bond.bond_id)

    if start:
        query = query.where(BondTrade.trade_date >= start)
        count_query = count_query.where(BondTrade.trade_date >= start)
    if end:
        query = query.where(BondTrade.trade_date <= end)
        count_query = count_query.where(BondTrade.trade_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondTrade.trade_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondTradeResponse.model_validate(t) for t in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── 12. GET /fixed-income/bonds/{cusip}/spread-history ─────────────────


@router.get(
    "/fixed-income/bonds/{cusip}/spread-history",
    response_model=PaginatedResponse,
)
async def get_spread_history(
    cusip: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
):
    """Get G-spread history for a bond."""
    bond_q = select(CorporateBond).where(CorporateBond.cusip == cusip)
    bond_result = await session.execute(bond_q)
    bond = bond_result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    query = select(BondEODPrice).where(
        BondEODPrice.bond_id == bond.bond_id,
        BondEODPrice.g_spread_bps.isnot(None),
    )
    count_query = select(BondEODPrice).where(
        BondEODPrice.bond_id == bond.bond_id,
        BondEODPrice.g_spread_bps.isnot(None),
    )

    if start:
        query = query.where(BondEODPrice.price_date >= start)
        count_query = count_query.where(BondEODPrice.price_date >= start)
    if end:
        query = query.where(BondEODPrice.price_date <= end)
        count_query = count_query.where(BondEODPrice.price_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(BondEODPrice.price_date.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        data=[BondEODPriceResponse.model_validate(p) for p in items],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── Analytics endpoint (bonus) ─────────────────────────────────────────


@router.get(
    "/fixed-income/bonds/{cusip}/analytics",
    response_model=BondAnalyticsResponse,
)
async def bond_analytics(
    cusip: str,
    price: float = Query(..., description="Current market price (% of par)"),
    treasury_yield: float | None = Query(None, description="Treasury benchmark yield for G-spread"),
    session: AsyncSession = Depends(get_session),
):
    """Compute YTM, YTW, duration, convexity, and G-spread for a bond."""
    query = select(CorporateBond).where(CorporateBond.cusip == cusip)
    result = await session.execute(query)
    bond = result.scalars().unique().one_or_none()

    if bond is None:
        raise HTTPException(
            status_code=404, detail=f"Bond with CUSIP {cusip} not found"
        )

    coupon = float(bond.coupon_rate) if bond.coupon_rate is not None else 0.0
    freq = bond.coupon_frequency if bond.coupon_frequency is not None else 2

    today = date.today()
    years_to_maturity = (bond.maturity_date - today).days / 365.25
    if years_to_maturity < 0:
        years_to_maturity = 0.0

    ytm = compute_ytm(price, coupon, 100.0, years_to_maturity, freq)

    # Build call schedule for YTW
    call_entries = []
    if bond.call_schedule:
        for cs in bond.call_schedule:
            call_years = (cs.call_date - today).days / 365.25
            call_price_val = float(cs.call_price) if cs.call_price is not None else 100.0
            if call_years > 0:
                call_entries.append({
                    "years_to_call": call_years,
                    "call_price": call_price_val,
                })

    ytw = compute_ytw(price, coupon, 100.0, years_to_maturity, call_entries or None, freq)
    mod_dur = compute_modified_duration(ytm, coupon, years_to_maturity, freq)
    mac_dur = compute_macaulay_duration(ytm, coupon, years_to_maturity, freq)
    convexity = compute_convexity(ytm, coupon, years_to_maturity, freq)

    g_spread_bps = None
    if treasury_yield is not None:
        g_spread_bps = compute_g_spread(ytm, treasury_yield)

    return BondAnalyticsResponse(
        cusip=cusip,
        price=price,
        ytm=ytm,
        ytw=ytw,
        modified_duration=mod_dur,
        macaulay_duration=mac_dur,
        convexity=convexity,
        g_spread_bps=g_spread_bps,
        years_to_maturity=round(years_to_maturity, 4),
    )
