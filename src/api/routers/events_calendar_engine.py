"""Events Calendar API endpoints (Pillar 2 Supplement – Part 5).

Aggregates events from the ``calendar_events`` table (the same backing table
used by the working ``calendar`` router) and merges/sorts them via the pure
``events_calendar`` engine. Read-only — does not affect the ``calendar`` router.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.events_calendar import get_unified_events, summarize_events
from src.models.calendar import CalendarEvent
from src.schemas.events_calendar import (
    EventsCalendarResponse,
    EventsSummaryResponse,
    UnifiedCalendarEvent,
)

router = APIRouter(tags=["Events Calendar"])


def _bucket_events(rows: list[CalendarEvent]) -> dict[str, list[dict]]:
    """Group DB rows into {source_type: [event dict]} for the engine."""
    events_by_source: dict[str, list[dict]] = {}
    for row in rows:
        source = row.event_type or "OTHER"
        events_by_source.setdefault(source, []).append({
            "event_id": str(row.event_id),
            "event_date": row.event_date,
            "title": (row.event_type or "Event").replace("_", " ").title(),
            "description": row.event_description,
            "entity_id": str(row.entity_id) if row.entity_id else None,
        })
    return events_by_source


@router.get(
    "/analytics/events",
    response_model=EventsCalendarResponse,
)
async def get_events(
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None, description="Start date"),
    end: date | None = Query(None, description="End date"),
    source_type: str | None = Query(None, description="Filter by event type"),
):
    """Return unified calendar events from the calendar_events table."""
    if not start:
        start = date.today()
    if not end:
        end = start + timedelta(days=30)

    query = select(CalendarEvent).where(
        CalendarEvent.event_date >= start,
        CalendarEvent.event_date <= end,
    )
    if source_type:
        query = query.where(CalendarEvent.event_type == source_type.upper())
    query = query.order_by(CalendarEvent.event_date.asc())

    rows = (await session.execute(query)).scalars().all()

    unified = get_unified_events(_bucket_events(rows), start_date=start, end_date=end)

    events = [
        UnifiedCalendarEvent(
            event_id=e.event_id,
            source_type=e.source_type,
            event_date=e.event_date,
            title=e.title,
            description=e.description,
            entity_id=e.entity_id,
            entity_name=e.entity_name,
            importance=e.importance,
        )
        for e in unified
    ]

    return EventsCalendarResponse(
        start_date=start,
        end_date=end,
        total_events=len(events),
        events=events,
    )


@router.get(
    "/analytics/events/summary",
    response_model=EventsSummaryResponse,
)
async def get_events_summary(
    session: AsyncSession = Depends(get_session),
    days: int = Query(7, ge=1, le=90, description="Number of days ahead"),
):
    """Return a summary of upcoming events grouped by source/event type."""
    start = date.today()
    end = start + timedelta(days=days)

    rows = (
        await session.execute(
            select(CalendarEvent).where(
                CalendarEvent.event_date >= start,
                CalendarEvent.event_date <= end,
            )
        )
    ).scalars().all()

    unified = get_unified_events(_bucket_events(rows), start_date=start, end_date=end)
    summary = summarize_events(unified)

    return EventsSummaryResponse(
        date_range=f"next {days} days",
        total_events=summary["total_events"],
        by_source=summary["by_source"],
    )
