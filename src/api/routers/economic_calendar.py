"""Economic Calendar API endpoints (Pillar 3 Phase 2)."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, nullslast
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.economic_calendar import EconomicRelease
from src.models.calendar import CalendarEvent
from src.schemas.economic_calendar import (
    EconomicCalendarListResponse,
    EconomicReleaseResponse,
)

router = APIRouter(tags=["Economic Calendar"])


# ── Static routes (MUST be before parametric) ────────────────────────


@router.get(
    "/news/calendar/economic",
    response_model=EconomicCalendarListResponse,
)
async def get_economic_calendar(
    session: AsyncSession = Depends(get_session),
    target_date: date | None = Query(None, alias="date", description="Target date (defaults to today)"),
    days_ahead: int = Query(7, ge=1, le=90, description="Number of days ahead"),
    category: str | None = Query(None, description="Filter by category"),
    importance: str | None = Query(None, description="Filter by importance (HIGH/MEDIUM/LOW)"),
):
    """Get upcoming economic releases."""
    d = target_date or date.today()
    end = d + timedelta(days=days_ahead)

    stmt = select(EconomicRelease).where(
        and_(
            EconomicRelease.release_date >= d,
            EconomicRelease.release_date <= end,
        )
    )

    if category:
        stmt = stmt.where(EconomicRelease.release_category == category)
    if importance:
        stmt = stmt.where(EconomicRelease.importance == importance)

    stmt = stmt.order_by(EconomicRelease.release_date)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    releases = [
        EconomicReleaseResponse(
            id=r.id,
            release_type=r.release_type,
            release_category=r.release_category,
            release_date=r.release_date,
            importance=r.importance,
            consensus_value=float(r.consensus_value) if r.consensus_value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            actual_value=float(r.actual_value) if r.actual_value is not None else None,
            surprise_value=float(r.surprise_value) if r.surprise_value is not None else None,
            surprise_magnitude=float(r.surprise_magnitude) if r.surprise_magnitude is not None else None,
            sector_sensitivity=r.sector_sensitivity,
            ai_summary=r.ai_summary,
        )
        for r in rows
    ]
    return EconomicCalendarListResponse(releases=releases, total_count=len(releases))


@router.get(
    "/news/calendar/economic/surprises",
    response_model=EconomicCalendarListResponse,
)
async def get_economic_surprises(
    session: AsyncSession = Depends(get_session),
    days_back: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Get recent economic data surprises."""
    today = date.today()
    start = today - timedelta(days=days_back)

    stmt = (
        select(EconomicRelease)
        .where(
            and_(
                EconomicRelease.release_date >= start,
                EconomicRelease.release_date <= today,
                EconomicRelease.surprise_value.isnot(None),
            )
        )
        .order_by(nullslast(EconomicRelease.surprise_magnitude.desc()))
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    releases = [
        EconomicReleaseResponse(
            id=r.id,
            release_type=r.release_type,
            release_category=r.release_category,
            release_date=r.release_date,
            importance=r.importance,
            consensus_value=float(r.consensus_value) if r.consensus_value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            actual_value=float(r.actual_value) if r.actual_value is not None else None,
            surprise_value=float(r.surprise_value) if r.surprise_value is not None else None,
            surprise_magnitude=float(r.surprise_magnitude) if r.surprise_magnitude is not None else None,
            sector_sensitivity=r.sector_sensitivity,
            ai_summary=r.ai_summary,
        )
        for r in rows
    ]
    return EconomicCalendarListResponse(releases=releases, total_count=len(releases))


@router.get(
    "/news/calendar/central-banks",
    response_model=list[dict],
)
async def get_central_bank_events(
    session: AsyncSession = Depends(get_session),
    days_ahead: int = Query(30, ge=1, le=180, description="Days ahead to look"),
):
    """Get upcoming central bank events (FOMC, ECB, BOJ, etc.)."""
    today = date.today()
    end = today + timedelta(days=days_ahead)

    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= end,
                CalendarEvent.event_type.in_([
                    "FOMC", "FOMC_MEETING", "CENTRAL_BANK",
                    "ECB_MEETING", "BOJ_MEETING", "BOE_MEETING",
                ]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]


@router.get(
    "/news/calendar/earnings",
    response_model=list[dict],
)
async def get_earnings_calendar_events(
    session: AsyncSession = Depends(get_session),
    days_ahead: int = Query(7, ge=1, le=90, description="Days ahead to look"),
):
    """Get upcoming earnings calendar events."""
    today = date.today()
    end = today + timedelta(days=days_ahead)

    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= end,
                CalendarEvent.event_type.in_(["EARNINGS", "EARNINGS_RELEASE"]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]


@router.get(
    "/news/calendar/regulatory",
    response_model=list[dict],
)
async def get_regulatory_calendar(
    session: AsyncSession = Depends(get_session),
    days_ahead: int = Query(30, ge=1, le=180, description="Days ahead to look"),
):
    """Get upcoming regulatory calendar events."""
    today = date.today()
    end = today + timedelta(days=days_ahead)

    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= end,
                CalendarEvent.event_type.in_([
                    "REGULATORY", "SEC_FILING_DEADLINE", "REGULATORY_HEARING",
                ]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]


@router.get(
    "/news/calendar/corporate",
    response_model=list[dict],
)
async def get_corporate_events(
    session: AsyncSession = Depends(get_session),
    days_ahead: int = Query(14, ge=1, le=90, description="Days ahead to look"),
):
    """Get upcoming corporate events (M&A, dividends, splits, etc.)."""
    today = date.today()
    end = today + timedelta(days=days_ahead)

    stmt = (
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.event_date >= today,
                CalendarEvent.event_date <= end,
                CalendarEvent.event_type.in_([
                    "DIVIDEND", "STOCK_SPLIT", "MERGER", "ACQUISITION",
                    "SPINOFF", "IPO", "SECONDARY_OFFERING",
                ]),
            )
        )
        .order_by(CalendarEvent.event_date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "event_id": str(r.event_id),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "event_type": r.event_type,
            "event_date": r.event_date.isoformat(),
            "event_description": r.event_description,
        }
        for r in rows
    ]


# ── Parametric routes ─────────────────────────────────────────────────


@router.get(
    "/news/calendar/economic/{release_id}",
    response_model=EconomicReleaseResponse,
)
async def get_economic_release_detail(
    release_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detail for a single economic release."""
    result = await session.execute(
        select(EconomicRelease).where(EconomicRelease.id == release_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Economic release not found")

    return EconomicReleaseResponse(
        id=r.id,
        release_type=r.release_type,
        release_category=r.release_category,
        release_date=r.release_date,
        importance=r.importance,
        consensus_value=float(r.consensus_value) if r.consensus_value is not None else None,
        prior_value=float(r.prior_value) if r.prior_value is not None else None,
        actual_value=float(r.actual_value) if r.actual_value is not None else None,
        surprise_value=float(r.surprise_value) if r.surprise_value is not None else None,
        surprise_magnitude=float(r.surprise_magnitude) if r.surprise_magnitude is not None else None,
        sector_sensitivity=r.sector_sensitivity,
        ai_summary=r.ai_summary,
    )
