"""D3 Company Fundamentals API endpoints (Spec 5.7)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_pagination, get_session
from src.api.utils.pagination import build_paginated_meta
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    Filing,
    FinancialPeriod,
    IncomeStatement,
    SegmentData,
)
from src.schemas.common import PaginatedResponse, PaginationParams
from src.schemas.fundamentals import (
    BalanceSheetResponse,
    CashFlowStatementResponse,
    FilingResponse,
    FinancialPeriodResponse,
    FundamentalsResponse,
    IncomeStatementResponse,
    SegmentDataResponse,
)

router = APIRouter(tags=["Fundamentals"])


# ── GET /v1/entities/{id}/filings ────────────────────────────────

@router.get("/entities/{entity_id}/filings", response_model=PaginatedResponse)
async def list_entity_filings(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    filing_type: str | None = Query(None),
    status: str | None = Query(None),
):
    """List filings for an entity."""
    query = select(Filing).where(Filing.entity_id == entity_id)
    count_query = select(Filing).where(Filing.entity_id == entity_id)

    if filing_type:
        query = query.where(Filing.filing_type == filing_type)
        count_query = count_query.where(Filing.filing_type == filing_type)
    if status:
        query = query.where(Filing.processing_status == status.upper())
        count_query = count_query.where(Filing.processing_status == status.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(Filing.filing_date.desc().nulls_last()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    filings = result.scalars().all()

    return PaginatedResponse(
        data=[FilingResponse.model_validate(f) for f in filings],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/filings/{filing_id} ──────────────────────────────────

@router.get("/filings/{filing_id}", response_model=FilingResponse)
async def get_filing(
    filing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single filing by ID."""
    result = await session.execute(select(Filing).where(Filing.filing_id == filing_id))
    filing = result.scalar_one_or_none()
    if not filing:
        raise HTTPException(status_code=404, detail=f"Filing '{filing_id}' not found")
    return FilingResponse.model_validate(filing)


# ── GET /v1/entities/{id}/fundamentals ────────────────────────────

@router.get("/entities/{entity_id}/fundamentals", response_model=list[FundamentalsResponse])
async def get_entity_fundamentals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    period_type: str | None = Query(None, description="ANNUAL or QUARTERLY"),
    fiscal_year: int | None = Query(None),
    limit: int = Query(default=4, ge=1, le=20),
):
    """Get fundamentals for an entity (latest periods)."""
    query = select(FinancialPeriod).where(FinancialPeriod.entity_id == entity_id)

    if period_type:
        query = query.where(FinancialPeriod.period_type == period_type.upper())
    if fiscal_year:
        query = query.where(FinancialPeriod.fiscal_year == fiscal_year)

    query = query.order_by(FinancialPeriod.period_end_date.desc()).limit(limit)
    result = await session.execute(query)
    periods = result.scalars().all()

    responses = []
    for period in periods:
        resp = FundamentalsResponse(
            period=FinancialPeriodResponse.model_validate(period),
            income_statement=IncomeStatementResponse.model_validate(period.income_statement) if period.income_statement else None,
            balance_sheet=BalanceSheetResponse.model_validate(period.balance_sheet) if period.balance_sheet else None,
            cash_flow=CashFlowStatementResponse.model_validate(period.cash_flow) if period.cash_flow else None,
        )
        responses.append(resp)

    return responses


# ── GET /v1/entities/{id}/fundamentals/income-statement ──────────

@router.get("/entities/{entity_id}/fundamentals/income-statement", response_model=PaginatedResponse)
async def get_income_statements(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    period_type: str | None = Query(None),
):
    """Get income statement series for an entity."""
    query = (
        select(IncomeStatement)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )
    count_query = (
        select(IncomeStatement)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )

    if period_type:
        query = query.where(FinancialPeriod.period_type == period_type.upper())
        count_query = count_query.where(FinancialPeriod.period_type == period_type.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(FinancialPeriod.period_end_date.desc()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    statements = result.scalars().all()

    return PaginatedResponse(
        data=[IncomeStatementResponse.model_validate(s) for s in statements],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/fundamentals/balance-sheet ─────────────

@router.get("/entities/{entity_id}/fundamentals/balance-sheet", response_model=PaginatedResponse)
async def get_balance_sheets(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    period_type: str | None = Query(None),
):
    """Get balance sheet series for an entity."""
    query = (
        select(BalanceSheet)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )
    count_query = (
        select(BalanceSheet)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )

    if period_type:
        query = query.where(FinancialPeriod.period_type == period_type.upper())
        count_query = count_query.where(FinancialPeriod.period_type == period_type.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(FinancialPeriod.period_end_date.desc()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    statements = result.scalars().all()

    return PaginatedResponse(
        data=[BalanceSheetResponse.model_validate(s) for s in statements],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/fundamentals/cash-flow ─────────────────

@router.get("/entities/{entity_id}/fundamentals/cash-flow", response_model=PaginatedResponse)
async def get_cash_flows(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    period_type: str | None = Query(None),
):
    """Get cash flow statement series for an entity."""
    query = (
        select(CashFlowStatement)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )
    count_query = (
        select(CashFlowStatement)
        .join(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
    )

    if period_type:
        query = query.where(FinancialPeriod.period_type == period_type.upper())
        count_query = count_query.where(FinancialPeriod.period_type == period_type.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(FinancialPeriod.period_end_date.desc()).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    statements = result.scalars().all()

    return PaginatedResponse(
        data=[CashFlowStatementResponse.model_validate(s) for s in statements],
        meta=build_paginated_meta(total_count, pagination),
    )


# ── GET /v1/entities/{id}/segments ───────────────────────────────

@router.get("/entities/{entity_id}/segments", response_model=PaginatedResponse)
async def get_entity_segments(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination),
    segment_type: str | None = Query(None),
):
    """Get segment data for an entity."""
    query = select(SegmentData).where(SegmentData.entity_id == entity_id)
    count_query = select(SegmentData).where(SegmentData.entity_id == entity_id)

    if segment_type:
        query = query.where(SegmentData.segment_type == segment_type.upper())
        count_query = count_query.where(SegmentData.segment_type == segment_type.upper())

    total_result = await session.execute(select(sa_func.count()).select_from(count_query.subquery()))
    total_count = total_result.scalar_one()

    offset = (pagination.page - 1) * pagination.page_size
    query = query.order_by(SegmentData.segment_name).offset(offset).limit(pagination.page_size)
    result = await session.execute(query)
    segments = result.scalars().all()

    return PaginatedResponse(
        data=[SegmentDataResponse.model_validate(s) for s in segments],
        meta=build_paginated_meta(total_count, pagination),
    )
