"""D2 Security Master API endpoints (Spec 4.8)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.api.utils.query_filters import escape_like
from src.models.entity import Entity
from src.models.security import (
    EODPrice,
    Security,
    SecurityIdentifier,
)
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.entity import EntityResponse
from src.schemas.security import (
    EODPriceResponse,
    SecurityBriefResponse,
    SecurityBulkLookupRequest,
    SecurityBulkLookupResponse,
    SecurityIdentifierResponse,
    SecurityResponse,
    SecuritySearchResponse,
    SecuritySearchResult,
    TranslateRequest,
    TranslateResponse,
    TranslateResult,
)

router = APIRouter(prefix="/securities", tags=["Securities"])


def _compute_relevance(name: str, query: str) -> float:
    """Basic relevance score: exact=1.0, starts-with=0.8, contains=0.5."""
    name_lower = name.lower() if name else ""
    q_lower = query.lower()
    if name_lower == q_lower:
        return 1.0
    if name_lower.startswith(q_lower):
        return 0.8
    return 0.5


# ── GET /v1/securities/search ──────────────────────────────────────
# NOTE: Declared before /{security_id} to avoid path-param collision.

@router.get("/search", response_model=SecuritySearchResponse)
async def search_securities(
    q: str = Query(..., min_length=1, description="Search query"),
    asset_class: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Fuzzy search for securities by name."""
    escaped_q = escape_like(q)

    # Left-join SecurityIdentifier to fetch ticker for each result
    ticker_ident = (
        select(SecurityIdentifier.security_id, SecurityIdentifier.identifier_value)
        .where(SecurityIdentifier.identifier_type == "TICKER")
        .subquery()
    )

    query = (
        select(Security, ticker_ident.c.identifier_value.label("ticker"))
        .outerjoin(
            ticker_ident,
            Security.security_id == ticker_ident.c.security_id,
        )
        .where(
            Security.name.ilike(f"%{escaped_q}%")
            | Security.short_name.ilike(f"%{escaped_q}%")
        )
    )

    if asset_class:
        query = query.where(Security.asset_class == asset_class.upper())
    if status:
        query = query.where(Security.status == status.upper())

    # Count
    total_result = await session.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total_count = total_result.scalar_one()

    # Paginate
    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Security.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    rows = result.all()

    results = [
        SecuritySearchResult(
            security_id=s.security_id,
            name=s.name,
            short_name=s.short_name,
            security_type=s.security_type,
            asset_class=s.asset_class,
            status=s.status,
            ticker=ticker,
            exchange=s.primary_exchange_mic,
            score=_compute_relevance(s.name, q),
        )
        for s, ticker in rows
    ]
    results.sort(key=lambda r: r.score, reverse=True)

    return SecuritySearchResponse(results=results, total=total_count, query=q)


# ── GET /v1/securities/{security_id} ──────────────────────────────

@router.get("/{security_id}", response_model=SecurityResponse)
async def get_security(
    security_id: uuid.UUID,
    expand: list[str] = Query(default=[]),
    session: AsyncSession = Depends(get_session),
):
    """Get a single security by ID with optional expansion.

    Supported expand values: identifiers, equity_details, fixed_income_details,
    credit_ratings, call_put_schedule
    """
    result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    security = result.scalar_one_or_none()
    if not security:
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    resp = SecurityResponse.model_validate(security)

    # Fetch ticker from SecurityIdentifier when expand=ticker is requested
    if "ticker" in expand:
        ticker_result = await session.execute(
            select(SecurityIdentifier.identifier_value).where(
                SecurityIdentifier.security_id == security_id,
                SecurityIdentifier.identifier_type == "TICKER",
            )
        )
        resp.ticker = ticker_result.scalar_one_or_none()

    # Only include expanded fields when explicitly requested
    if "identifiers" not in expand:
        resp.identifiers = None
    if "equity_details" not in expand:
        resp.equity_details = None
    if "fixed_income_details" not in expand:
        resp.fixed_income_details = None
    if "credit_ratings" not in expand:
        resp.credit_ratings = None
    if "call_put_schedule" not in expand:
        resp.call_put_schedule = None

    return resp


# ── GET /v1/securities ─────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
async def list_securities(
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    isin: str | None = Query(None, description="Filter by ISIN"),
    cusip: str | None = Query(None, description="Filter by CUSIP"),
    figi: str | None = Query(None, description="Filter by FIGI"),
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    asset_class: str | None = Query(None),
    status: str | None = Query(None),
):
    """List / filter securities.

    Identifier-based filters (isin, cusip, figi, ticker) join through
    security_identifiers.
    """
    query = select(Security)
    count_query = select(Security)

    # Identifier-based filters
    identifier_filters: list[tuple[str, str]] = []
    if isin:
        identifier_filters.append(("ISIN", isin))
    if cusip:
        identifier_filters.append(("CUSIP", cusip))
    if figi:
        identifier_filters.append(("FIGI", figi))
    if ticker:
        identifier_filters.append(("TICKER", ticker))

    if identifier_filters:
        id_conditions = []
        for id_type, id_value in identifier_filters:
            sub = select(SecurityIdentifier.security_id).where(
                SecurityIdentifier.identifier_type == id_type,
                SecurityIdentifier.identifier_value == id_value,
            )
            id_conditions.append(Security.security_id.in_(sub))
        combined = or_(*id_conditions) if len(id_conditions) > 1 else id_conditions[0]
        query = query.where(combined)
        count_query = count_query.where(combined)

    # Direct column filters
    if asset_class:
        query = query.where(Security.asset_class == asset_class.upper())
        count_query = count_query.where(Security.asset_class == asset_class.upper())
    if status:
        query = query.where(Security.status == status.upper())
        count_query = count_query.where(Security.status == status.upper())

    # Count
    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    # Paginate
    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Security.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    securities = result.scalars().all()

    return PaginatedResponse(
        data=[SecurityBriefResponse.model_validate(s) for s in securities],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/identifiers ────────────────────────────

@router.get(
    "/{security_id}/identifiers",
    response_model=list[SecurityIdentifierResponse],
)
async def get_security_identifiers(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get all identifier mappings for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    result = await session.execute(
        select(SecurityIdentifier)
        .where(SecurityIdentifier.security_id == security_id)
        .order_by(SecurityIdentifier.identifier_type)
    )
    identifiers = result.scalars().all()

    return [SecurityIdentifierResponse.model_validate(i) for i in identifiers]


# ── GET /v1/securities/{id}/issuer ─────────────────────────────────

@router.get("/{security_id}/issuer", response_model=EntityResponse)
async def get_security_issuer(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the issuer entity for a security."""
    sec_result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    security = sec_result.scalar_one_or_none()
    if not security:
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    if not security.issuer_entity_id:
        raise HTTPException(
            status_code=404,
            detail=f"Security '{security_id}' has no linked issuer",
        )

    ent_result = await session.execute(
        select(Entity).where(Entity.entity_id == security.issuer_entity_id)
    )
    entity = ent_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=404,
            detail=f"Issuer entity '{security.issuer_entity_id}' not found",
        )

    return EntityResponse.model_validate(entity)


# ── GET /v1/securities/{id}/related ────────────────────────────────

@router.get("/{security_id}/related", response_model=PaginatedResponse)
async def get_related_securities(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
):
    """Get securities related to this one (same issuer)."""
    # Fetch the security to find its issuer
    sec_result = await session.execute(
        select(Security).where(Security.security_id == security_id)
    )
    security = sec_result.scalar_one_or_none()
    if not security:
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    if not security.issuer_entity_id:
        return PaginatedResponse(
            data=[],
            meta=build_paginated_meta(0, pagination),
        )

    # All securities by the same issuer, excluding this one
    query = select(Security).where(
        Security.issuer_entity_id == security.issuer_entity_id,
        Security.security_id != security_id,
    )
    count_query = select(Security).where(
        Security.issuer_entity_id == security.issuer_entity_id,
        Security.security_id != security_id,
    )

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Security.name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    related = result.scalars().all()

    return PaginatedResponse(
        data=[SecurityBriefResponse.model_validate(s) for s in related],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/prices ─────────────────────────────────

@router.get("/{security_id}/prices", response_model=PaginatedResponse)
async def get_security_prices(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    start: date | None = Query(None, description="Start date (inclusive)"),
    end: date | None = Query(None, description="End date (inclusive)"),
):
    """Get end-of-day price history for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    query = select(EODPrice).where(EODPrice.security_id == security_id)
    count_query = select(EODPrice).where(EODPrice.security_id == security_id)

    if start:
        query = query.where(EODPrice.price_date >= start)
        count_query = count_query.where(EODPrice.price_date >= start)
    if end:
        query = query.where(EODPrice.price_date <= end)
        count_query = count_query.where(EODPrice.price_date <= end)

    total_result = await session.execute(
        select(sa_func.count()).select_from(count_query.subquery())
    )
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = (
        query.order_by(EODPrice.price_date.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(query)
    prices = result.scalars().all()

    return PaginatedResponse(
        data=[EODPriceResponse.model_validate(p) for p in prices],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/securities/{id}/prices/latest ──────────────────────────

@router.get("/{security_id}/prices/latest", response_model=EODPriceResponse)
async def get_latest_price(
    security_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the most recent end-of-day price for a security."""
    # Verify security exists
    sec_result = await session.execute(
        select(Security.security_id).where(Security.security_id == security_id)
    )
    if not sec_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404, detail=f"Security '{security_id}' not found"
        )

    result = await session.execute(
        select(EODPrice)
        .where(EODPrice.security_id == security_id)
        .order_by(EODPrice.price_date.desc())
        .limit(1)
    )
    price = result.scalar_one_or_none()
    if not price:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for security '{security_id}'",
        )

    return EODPriceResponse.model_validate(price)


# ── POST /v1/securities/bulk-lookup ────────────────────────────────

@router.post("/bulk-lookup", response_model=SecurityBulkLookupResponse)
async def bulk_lookup_securities(
    body: SecurityBulkLookupRequest,
    session: AsyncSession = Depends(get_session),
):
    """Batch identifier lookup.

    Accepts a list of (type, value) pairs and returns the corresponding
    securities (or null for unmatched identifiers).
    """
    results: list[SecurityResponse | None] = []

    for lookup in body.identifiers:
        ident_result = await session.execute(
            select(SecurityIdentifier).where(
                SecurityIdentifier.identifier_type == lookup.type,
                SecurityIdentifier.identifier_value == lookup.value,
            )
        )
        ident = ident_result.scalar_one_or_none()

        if ident is None:
            results.append(None)
            continue

        sec_result = await session.execute(
            select(Security).where(Security.security_id == ident.security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security:
            results.append(SecurityResponse.model_validate(security))
        else:
            results.append(None)

    return SecurityBulkLookupResponse(results=results)


# ── POST /v1/securities/translate ──────────────────────────────────

@router.post("/translate", response_model=TranslateResponse)
async def translate_identifiers(
    body: TranslateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Translate between identifier types.

    Given a source identifier (e.g. ISIN), look up the security and return
    the requested target identifier types.
    """
    # Find the security via the source identifier
    ident_result = await session.execute(
        select(SecurityIdentifier).where(
            SecurityIdentifier.identifier_type == body.source_type,
            SecurityIdentifier.identifier_value == body.source_value,
        )
    )
    source_ident = ident_result.scalar_one_or_none()
    if not source_ident:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No security found with {body.source_type}='{body.source_value}'"
            ),
        )

    # Fetch all identifiers for that security
    all_idents_result = await session.execute(
        select(SecurityIdentifier).where(
            SecurityIdentifier.security_id == source_ident.security_id
        )
    )
    all_idents = all_idents_result.scalars().all()

    # Build a lookup map
    ident_map: dict[str, str] = {
        i.identifier_type: i.identifier_value for i in all_idents
    }

    translations = []
    for t in body.target_types:
        if t in ident_map:
            translations.append(TranslateResult(type=t, value=ident_map[t]))
        else:
            translations.append(
                TranslateResult(
                    type=t,
                    value=None,
                    warning=f"Identifier type '{t}' not found for this security",
                )
            )

    return TranslateResponse(
        source_type=body.source_type,
        source_value=body.source_value,
        translations=translations,
    )
