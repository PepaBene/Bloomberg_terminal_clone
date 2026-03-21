"""Tests for calendar event models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.calendar import CalendarEvent
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_calendar_event(session):
    """Test creating a calendar event."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Calendar Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    event_id = uuid.uuid4()
    event = CalendarEvent(
        event_id=event_id,
        entity_id=entity_id,
        event_type="DIVIDEND_EX_DATE",
        event_date=date(2026, 3, 15),
        event_description="Q1 2026 dividend ex-date",
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.event_id == event_id)
    )
    fetched = result.scalar_one()
    assert fetched.event_type == "DIVIDEND_EX_DATE"
    assert fetched.event_date == date(2026, 3, 15)
    assert fetched.event_description == "Q1 2026 dividend ex-date"


@pytest.mark.asyncio
async def test_list_events_by_date_range(session):
    """Test querying calendar events within a date range."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Range Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for month in [1, 3, 6, 9, 12]:
        session.add(CalendarEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            event_type="EARNINGS_ANNOUNCEMENT",
            event_date=date(2026, month, 15),
        ))
    await session.flush()

    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.entity_id == entity_id)
        .where(CalendarEvent.event_date >= date(2026, 2, 1))
        .where(CalendarEvent.event_date <= date(2026, 7, 1))
    )
    events = result.scalars().all()
    assert len(events) == 2  # March and June


@pytest.mark.asyncio
async def test_list_events_by_type(session):
    """Test querying calendar events by type."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Type Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="STOCK_SPLIT",
        event_date=date(2026, 5, 1),
    ))
    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="DIVIDEND_EX_DATE",
        event_date=date(2026, 5, 10),
    ))
    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="DIVIDEND_EX_DATE",
        event_date=date(2026, 8, 10),
    ))
    await session.flush()

    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.entity_id == entity_id)
        .where(CalendarEvent.event_type == "DIVIDEND_EX_DATE")
    )
    events = result.scalars().all()
    assert len(events) == 2
