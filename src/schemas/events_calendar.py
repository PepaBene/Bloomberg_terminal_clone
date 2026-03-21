"""Pydantic schemas for events calendar."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class UnifiedCalendarEvent(BaseModel):
    """A single event from any source."""
    event_id: str
    source_type: str  # CALENDAR_EVENT, EARNINGS_ANNOUNCEMENT, etc.
    event_date: date
    title: str
    description: str | None = None
    entity_id: uuid.UUID | None = None
    entity_name: str | None = None
    importance: str | None = None  # HIGH, MEDIUM, LOW


class EventsCalendarResponse(BaseModel):
    """Events calendar response."""
    start_date: date
    end_date: date
    total_events: int
    events: list[UnifiedCalendarEvent] = []


class EventsSummaryResponse(BaseModel):
    """Summary of upcoming events."""
    date_range: str
    total_events: int
    by_source: dict[str, int] = {}
