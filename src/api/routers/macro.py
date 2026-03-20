"""D7 Macroeconomic Data API endpoints (Spec 9.7)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.api.utils.query_filters import escape_like
from src.models.macro import CentralBankPolicy, MacroIndicator, MacroValue
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.macro import (
    CentralBankPolicyResponse,
    CentralBankRateHistoryResponse,
    MacroBulkRequest,
    MacroIndicatorBriefResponse,
    MacroIndicatorResponse,
    MacroIndicatorSearchResponse,
    MacroLatestValueResponse,
    MacroValueResponse,
)

router = APIRouter(prefix="/macro", tags=["Macro"])


# ── GET /v1/macro/indicators ─────────────────────────────────────

@router.get("/indicators", response_model=PaginatedResponse)
async def list_indicators(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    category: str | None = Query(None, description="Filter by category (e.g. GDP, RATES)"),
    country: str | None = Query(None, description="Filter by ISO alpha-2 country code"),
    frequency: str | None = Query(None, description="Filter by frequency (DAILY, MONTHLY, etc.)"),
    is_active: bool | None = Query(None, description="Filter by active status"),
):
    """List macroeconomic indicators with optional filters."""
    query = select(MacroIndicator)
    count_query = select(MacroIndicator)

    if category:
        query = query.where(MacroIndicator.category == category.upper())
        count_query = count_query.where(MacroIndicator.category == category.upper())
    if country:
        query = query.where(MacroIndicator.country_code == country.upper())
        count_query = count_query.where(MacroIndicator.country_code == country.upper())
    if frequency:
        query = query.where(MacroIndicator.frequency == frequency.upper())
        count_query = count_query.where(MacroIndicator.frequency == frequency.upper())
    if is_active is not None:
        query = query.where(MacroIndicator.is_active == is_active)
        count_query = count_query.where(MacroIndicator.is_active == is_active)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(MacroIndicator.indicator_code).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    indicators = result.scalars().all()

    return PaginatedResponse(
        data=[MacroIndicatorBriefResponse.model_validate(i) for i in indicators],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/macro/indicators/search ──────────────────────────────

@router.get("/indicators/search", response_model=MacroIndicatorSearchResponse)
async def search_indicators(
    q: str = Query(..., min_length=1, description="Search query"),
    category: str | None = Query(None),
    country: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Search macro indicators by name or code."""
    escaped_q = escape_like(q)
    query = select(MacroIndicator).where(
        MacroIndicator.name.ilike(f"%{escaped_q}%")
        | MacroIndicator.indicator_code.ilike(f"%{escaped_q}%")
        | MacroIndicator.short_name.ilike(f"%{escaped_q}%")
    )

    if category:
        query = query.where(MacroIndicator.category == category.upper())
    if country:
        query = query.where(MacroIndicator.country_code == country.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(MacroIndicator.indicator_code).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    indicators = result.scalars().all()

    return MacroIndicatorSearchResponse(
        results=[MacroIndicatorBriefResponse.model_validate(i) for i in indicators],
        total=total_count,
        query=q,
    )


# ── GET /v1/macro/indicators/{code} ──────────────────────────────

@router.get("/indicators/{code}", response_model=MacroIndicatorResponse)
async def get_indicator(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single macro indicator by code."""
    result = await session.execute(
        select(MacroIndicator).where(MacroIndicator.indicator_code == code.upper())
    )
    indicator = result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")
    return MacroIndicatorResponse.model_validate(indicator)


# ── GET /v1/macro/indicators/{code}/values ───────────────────────

@router.get("/indicators/{code}/values", response_model=PaginatedResponse)
async def get_indicator_values(
    code: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    transformation: str | None = Query(
        None,
        description="Transformation: LEVEL, YOY, MOM, QOQ. "
        "All transform values are included in each record; use this to select a primary value.",
    ),
):
    """Get time series values for a macro indicator.

    All transformation variants (value_yoy, value_yoy_percent, value_mom,
    value_mom_percent, value_qoq_annualized) are returned in every record.
    When ``transformation`` is specified, the ``value`` field in each record
    is replaced with the requested transform column.
    """
    # Find indicator
    ind_result = await session.execute(
        select(MacroIndicator).where(MacroIndicator.indicator_code == code.upper())
    )
    indicator = ind_result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    query = select(MacroValue).where(MacroValue.indicator_id == indicator.indicator_id)
    count_query = select(MacroValue).where(MacroValue.indicator_id == indicator.indicator_id)

    if start_date:
        query = query.where(MacroValue.observation_date >= start_date)
        count_query = count_query.where(MacroValue.observation_date >= start_date)
    if end_date:
        query = query.where(MacroValue.observation_date <= end_date)
        count_query = count_query.where(MacroValue.observation_date <= end_date)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(MacroValue.observation_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    values = result.scalars().all()

    data = [MacroValueResponse.model_validate(v) for v in values]

    # Apply transformation: override the primary ``value`` field with the
    # requested transform column so callers get the desired series directly.
    _TRANSFORM_FIELD = {
        "YOY": "value_yoy_percent",
        "MOM": "value_mom_percent",
        "QOQ": "value_qoq_annualized",
    }
    if transformation and transformation.upper() in _TRANSFORM_FIELD:
        field = _TRANSFORM_FIELD[transformation.upper()]
        for record in data:
            transformed = getattr(record, field, None)
            if transformed is not None:
                record.value = transformed

    return PaginatedResponse(
        data=data,
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/macro/indicators/{code}/latest ───────────────────────

@router.get("/indicators/{code}/latest", response_model=MacroLatestValueResponse)
async def get_indicator_latest(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the most recent value for a macro indicator."""
    ind_result = await session.execute(
        select(MacroIndicator).where(MacroIndicator.indicator_code == code.upper())
    )
    indicator = ind_result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    val_result = await session.execute(
        select(MacroValue)
        .where(MacroValue.indicator_id == indicator.indicator_id)
        .order_by(MacroValue.observation_date.desc())
        .limit(1)
    )
    latest = val_result.scalar_one_or_none()
    if not latest:
        raise HTTPException(status_code=404, detail=f"No values found for indicator '{code}'")

    change = None
    change_percent = None
    if latest.previous_value is not None:
        change = float(latest.value) - float(latest.previous_value)
        if float(latest.previous_value) != 0:
            change_percent = (change / float(latest.previous_value)) * 100

    return MacroLatestValueResponse(
        indicator_code=indicator.indicator_code,
        indicator_name=indicator.name,
        observation_date=latest.observation_date,
        value=float(latest.value),
        previous_value=float(latest.previous_value) if latest.previous_value else None,
        change=change,
        change_percent=change_percent,
        unit=indicator.unit,
        frequency=indicator.frequency,
        source=latest.source,
    )


# ── GET /v1/macro/indicators/{code}/vintages ─────────────────────

@router.get("/indicators/{code}/vintages", response_model=PaginatedResponse)
async def get_indicator_vintages(
    code: str,
    observation_date: date = Query(..., description="Observation date to get vintages for"),
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get revision history (vintages) for a specific observation date."""
    ind_result = await session.execute(
        select(MacroIndicator).where(MacroIndicator.indicator_code == code.upper())
    )
    indicator = ind_result.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    query = select(MacroValue).where(
        MacroValue.indicator_id == indicator.indicator_id,
        MacroValue.observation_date == observation_date,
    )
    count_query = select(MacroValue).where(
        MacroValue.indicator_id == indicator.indicator_id,
        MacroValue.observation_date == observation_date,
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(MacroValue.vintage_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    values = result.scalars().all()

    return PaginatedResponse(
        data=[MacroValueResponse.model_validate(v) for v in values],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/macro/central-banks ──────────────────────────────────

@router.get("/central-banks", response_model=list[str])
async def list_central_banks(
    session: AsyncSession = Depends(get_session),
):
    """List all central banks with policy records."""
    result = await session.execute(
        select(CentralBankPolicy.bank_code).distinct().order_by(CentralBankPolicy.bank_code)
    )
    return [row[0] for row in result.all()]


# ── GET /v1/macro/central-banks/{code}/meetings ──────────────────

@router.get("/central-banks/{code}/meetings", response_model=PaginatedResponse)
async def get_central_bank_meetings(
    code: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
):
    """Get meeting history for a central bank."""
    query = select(CentralBankPolicy).where(
        CentralBankPolicy.bank_code == code.upper()
    )
    count_query = select(CentralBankPolicy).where(
        CentralBankPolicy.bank_code == code.upper()
    )

    if start_date:
        query = query.where(CentralBankPolicy.meeting_date >= start_date)
        count_query = count_query.where(CentralBankPolicy.meeting_date >= start_date)
    if end_date:
        query = query.where(CentralBankPolicy.meeting_date <= end_date)
        count_query = count_query.where(CentralBankPolicy.meeting_date <= end_date)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(CentralBankPolicy.meeting_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    meetings = result.scalars().all()

    return PaginatedResponse(
        data=[CentralBankPolicyResponse.model_validate(m) for m in meetings],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/macro/central-banks/{code}/rates ─────────────────────

@router.get("/central-banks/{code}/rates", response_model=CentralBankRateHistoryResponse)
async def get_central_bank_rates(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get rate history for a central bank."""
    result = await session.execute(
        select(CentralBankPolicy)
        .where(CentralBankPolicy.bank_code == code.upper())
        .order_by(CentralBankPolicy.meeting_date.desc())
    )
    meetings = result.scalars().all()

    if not meetings:
        raise HTTPException(status_code=404, detail=f"No policy records for bank '{code}'")

    latest = meetings[0]
    last_change = next(
        (m for m in meetings if m.rate_change and float(m.rate_change) != 0),
        None,
    )

    return CentralBankRateHistoryResponse(
        bank_code=code.upper(),
        meetings=[CentralBankPolicyResponse.model_validate(m) for m in meetings],
        current_rate=float(latest.policy_rate) if latest.policy_rate else None,
        last_change_date=last_change.meeting_date if last_change else None,
        last_change_direction=last_change.rate_direction if last_change else None,
    )


# ── GET /v1/macro/central-banks/{code}/latest ────────────────────

@router.get("/central-banks/{code}/latest", response_model=CentralBankPolicyResponse)
async def get_central_bank_latest(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest policy decision for a central bank."""
    result = await session.execute(
        select(CentralBankPolicy)
        .where(CentralBankPolicy.bank_code == code.upper())
        .order_by(CentralBankPolicy.meeting_date.desc())
        .limit(1)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"No policy records for bank '{code}'")
    return CentralBankPolicyResponse.model_validate(policy)


# ── POST /v1/macro/bulk ──────────────────────────────────────────

@router.post("/bulk", response_model=dict)
async def bulk_macro_data(
    body: MacroBulkRequest,
    session: AsyncSession = Depends(get_session),
):
    """Batch retrieval of macro data for multiple indicators."""
    results = {}
    for code in body.indicator_codes:
        ind_result = await session.execute(
            select(MacroIndicator).where(MacroIndicator.indicator_code == code.upper())
        )
        indicator = ind_result.scalar_one_or_none()
        if not indicator:
            results[code] = {"error": f"Indicator '{code}' not found"}
            continue

        query = select(MacroValue).where(MacroValue.indicator_id == indicator.indicator_id)
        if body.start_date:
            query = query.where(MacroValue.observation_date >= body.start_date)
        if body.end_date:
            query = query.where(MacroValue.observation_date <= body.end_date)

        query = query.order_by(MacroValue.observation_date.desc()).limit(100)
        val_result = await session.execute(query)
        values = val_result.scalars().all()

        results[code] = {
            "indicator": MacroIndicatorBriefResponse.model_validate(indicator).model_dump(mode="json"),
            "values": [MacroValueResponse.model_validate(v).model_dump(mode="json") for v in values],
        }

    return {"data": results}
