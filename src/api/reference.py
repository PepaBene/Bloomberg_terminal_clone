"""D8 Reference & Classification Data API endpoints (Spec 10.8)."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.cache.redis_cache import cache
from src.config import settings

logger = logging.getLogger(__name__)
from src.models.reference import (
    Country,
    Currency,
    Exchange,
    GICSClassification,
    NAICSCode,
    SICCode,
    TradingCalendar,
    TradingDay,
)
from src.schemas.common import PaginatedMeta, PaginatedResponse, PaginationParams
from src.schemas.reference import (
    CountryResponse,
    CurrencyResponse,
    ExchangeResponse,
    GICSResponse,
    GICSSectorResponse,
    IsTradingDayResponse,
    NAICSResponse,
    SICResponse,
    TradingDayResponse,
)

router = APIRouter(prefix="/reference", tags=["Reference Data"])


# ── Geographic ──────────────────────────────────────────────────────

@router.get("/countries", response_model=PaginatedResponse)
async def list_countries(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    continent: str | None = Query(None),
    region: str | None = Query(None),
    development_status: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    """List all countries with optional filtering."""
    query = select(Country)
    count_query = select(Country)

    if continent:
        query = query.where(Country.continent == continent)
        count_query = count_query.where(Country.continent == continent)
    if region:
        query = query.where(Country.region == region)
        count_query = count_query.where(Country.region == region)
    if development_status:
        query = query.where(Country.development_status == development_status)
        count_query = count_query.where(Country.development_status == development_status)
    if is_active is not None:
        query = query.where(Country.is_active == is_active)
        count_query = count_query.where(Country.is_active == is_active)

    # Count
    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    # Paginate
    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Country.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    countries = result.scalars().all()

    return PaginatedResponse(
        data=[CountryResponse.model_validate(c) for c in countries],
        meta=PaginatedMeta(
            request_id="",  # Filled by middleware
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/countries/{code}", response_model=CountryResponse)
async def get_country(code: str, session: AsyncSession = Depends(get_session)):
    """Get a single country by ISO 3166-1 alpha-2 code."""
    cache_key = cache.make_key("ref", "country", code.upper())
    cached = await cache.get(cache_key)
    if cached:
        return CountryResponse(**cached)

    result = await session.execute(
        select(Country).where(Country.country_code_alpha2 == code.upper())
    )
    country = result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail=f"Country '{code}' not found")

    resp = CountryResponse.model_validate(country)
    await cache.set(cache_key, resp.model_dump(mode="json"), ttl=settings.CACHE_TTL_REFERENCE)
    return resp


@router.get("/regions")
async def list_regions(session: AsyncSession = Depends(get_session)):
    """Get distinct region names."""
    result = await session.execute(
        select(distinct(Country.region))
        .where(Country.region.isnot(None))
        .order_by(Country.region)
    )
    return {"data": [r for (r,) in result.all()]}


# ── Currencies ──────────────────────────────────────────────────────

@router.get("/currencies", response_model=PaginatedResponse)
async def list_currencies(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    is_active: bool | None = Query(None),
):
    """List all currencies."""
    query = select(Currency)
    if is_active is not None:
        query = query.where(Currency.is_active == is_active)

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = query.order_by(Currency.currency_code).offset(offset).limit(pagination.page_size)
    result = await session.execute(items_query)
    currencies = result.scalars().all()

    return PaginatedResponse(
        data=[CurrencyResponse.model_validate(c) for c in currencies],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/currencies/{code}", response_model=CurrencyResponse)
async def get_currency(code: str, session: AsyncSession = Depends(get_session)):
    """Get a single currency by ISO 4217 code."""
    cache_key = cache.make_key("ref", "currency", code.upper())
    cached = await cache.get(cache_key)
    if cached:
        return CurrencyResponse(**cached)

    result = await session.execute(
        select(Currency).where(Currency.currency_code == code.upper())
    )
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail=f"Currency '{code}' not found")

    resp = CurrencyResponse.model_validate(currency)
    await cache.set(cache_key, resp.model_dump(mode="json"), ttl=settings.CACHE_TTL_REFERENCE)
    return resp


# ── Exchanges ───────────────────────────────────────────────────────

@router.get("/exchanges", response_model=PaginatedResponse)
async def list_exchanges(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    country: str | None = Query(None),
    status: str | None = Query(None),
    market_type: str | None = Query(None),
):
    """List exchanges with optional filtering."""
    query = select(Exchange)
    if country:
        query = query.where(Exchange.country == country.upper())
    if status:
        query = query.where(Exchange.status == status.upper())
    if market_type:
        query = query.where(Exchange.market_type == market_type.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = query.order_by(Exchange.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(items_query)
    exchanges = result.scalars().all()

    return PaginatedResponse(
        data=[ExchangeResponse.model_validate(e) for e in exchanges],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/exchanges/{mic}", response_model=ExchangeResponse)
async def get_exchange(mic: str, session: AsyncSession = Depends(get_session)):
    """Get a single exchange by MIC code."""
    cache_key = cache.make_key("ref", "exchange", mic.upper())
    cached = await cache.get(cache_key)
    if cached:
        return ExchangeResponse(**cached)

    result = await session.execute(
        select(Exchange).where(Exchange.mic == mic.upper())
    )
    exchange = result.scalar_one_or_none()
    if not exchange:
        raise HTTPException(status_code=404, detail=f"Exchange '{mic}' not found")

    resp = ExchangeResponse.model_validate(exchange)
    await cache.set(cache_key, resp.model_dump(mode="json"), ttl=settings.CACHE_TTL_REFERENCE)
    return resp


# ── Classifications ─────────────────────────────────────────────────

@router.get("/gics", response_model=PaginatedResponse)
async def list_gics(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    sector_code: str | None = Query(None),
    industry_group_code: str | None = Query(None),
):
    """List full GICS hierarchy."""
    query = select(GICSClassification)
    if sector_code:
        query = query.where(GICSClassification.sector_code == sector_code)
    if industry_group_code:
        query = query.where(GICSClassification.industry_group_code == industry_group_code)

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = (
        query.order_by(GICSClassification.sub_industry_code)
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(items_query)
    gics = result.scalars().all()

    return PaginatedResponse(
        data=[GICSResponse.model_validate(g) for g in gics],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/gics/sectors")
async def list_gics_sectors(session: AsyncSession = Depends(get_session)):
    """List the 11 GICS sectors."""
    result = await session.execute(
        select(
            distinct(GICSClassification.sector_code),
            GICSClassification.sector_name,
            GICSClassification.sector_description,
        ).order_by(GICSClassification.sector_code)
    )
    sectors = [
        GICSSectorResponse(
            sector_code=row[0], sector_name=row[1], sector_description=row[2]
        )
        for row in result.all()
    ]
    return {"data": sectors}


@router.get("/gics/{code}", response_model=GICSResponse)
async def get_gics(code: str, session: AsyncSession = Depends(get_session)):
    """Get a single GICS classification by sub-industry code."""
    cache_key = cache.make_key("ref", "gics", code)
    cached = await cache.get(cache_key)
    if cached:
        return GICSResponse(**cached)

    result = await session.execute(
        select(GICSClassification).where(
            GICSClassification.sub_industry_code == code
        )
    )
    gics = result.scalar_one_or_none()
    if not gics:
        raise HTTPException(status_code=404, detail=f"GICS code '{code}' not found")

    resp = GICSResponse.model_validate(gics)
    await cache.set(cache_key, resp.model_dump(mode="json"), ttl=settings.CACHE_TTL_REFERENCE)
    return resp


@router.get("/sic", response_model=PaginatedResponse)
async def list_sic_codes(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    division: str | None = Query(None),
):
    """List SIC codes."""
    query = select(SICCode)
    if division:
        query = query.where(SICCode.division == division.upper())

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = query.order_by(SICCode.sic_code).offset(offset).limit(pagination.page_size)
    result = await session.execute(items_query)
    codes = result.scalars().all()

    return PaginatedResponse(
        data=[SICResponse.model_validate(c) for c in codes],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/naics", response_model=PaginatedResponse)
async def list_naics_codes(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """List NAICS codes."""
    query = select(NAICSCode)

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = query.order_by(NAICSCode.naics_code).offset(offset).limit(pagination.page_size)
    result = await session.execute(items_query)
    codes = result.scalars().all()

    return PaginatedResponse(
        data=[NAICSResponse.model_validate(c) for c in codes],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


# ── Calendars ───────────────────────────────────────────────────────

@router.get("/calendars/{calendar_code}/dates", response_model=PaginatedResponse)
async def list_trading_days(
    calendar_code: str,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    year: int | None = Query(None),
    month: int | None = Query(None),
):
    """Get trading days for a calendar."""
    # Find calendar
    cal_result = await session.execute(
        select(TradingCalendar).where(
            TradingCalendar.calendar_code == calendar_code.upper()
        )
    )
    calendar = cal_result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(
            status_code=404, detail=f"Calendar '{calendar_code}' not found"
        )

    query = select(TradingDay).where(TradingDay.calendar_id == calendar.calendar_id)
    if year:
        from sqlalchemy import extract

        query = query.where(extract("year", TradingDay.date) == year)
    if month:
        from sqlalchemy import extract

        query = query.where(extract("month", TradingDay.date) == month)

    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    items_query = query.order_by(TradingDay.date).offset(offset).limit(pagination.page_size)
    result = await session.execute(items_query)
    days = result.scalars().all()

    return PaginatedResponse(
        data=[TradingDayResponse.model_validate(d) for d in days],
        meta=PaginatedMeta(
            request_id="",
            processing_time_ms=0,
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total_count + pagination.page_size - 1) // pagination.page_size,
        ),
    )


@router.get("/calendars/{calendar_code}/is-trading-day")
async def is_trading_day(
    calendar_code: str,
    date: date = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Check if a specific date is a trading day."""
    cal_result = await session.execute(
        select(TradingCalendar).where(
            TradingCalendar.calendar_code == calendar_code.upper()
        )
    )
    calendar = cal_result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(
            status_code=404, detail=f"Calendar '{calendar_code}' not found"
        )

    day_result = await session.execute(
        select(TradingDay).where(
            TradingDay.calendar_id == calendar.calendar_id,
            TradingDay.date == date,
        )
    )
    day = day_result.scalar_one_or_none()

    if not day:
        # Date not in calendar — assume non-trading day
        return IsTradingDayResponse(
            date=date,
            calendar_code=calendar_code.upper(),
            is_trading_day=False,
        )

    return IsTradingDayResponse(
        date=date,
        calendar_code=calendar_code.upper(),
        is_trading_day=day.is_trading_day,
        is_half_day=day.is_half_day,
        holiday_name=day.holiday_name,
    )
