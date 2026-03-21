"""Tests for Calendar API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.calendar import CalendarEvent
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_list_corporate_action_events_empty(client):
    """Test listing calendar corporate action events when DB is empty."""
    response = await client.get("/v1/calendar/corporate-actions")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_corporate_action_events(client, session):
    """Test listing calendar events filtered by event type."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Calendar API Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="DIVIDEND_EX_DATE",
        event_date=date(2026, 3, 15),
    ))
    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="STOCK_SPLIT",
        event_date=date(2026, 4, 1),
    ))
    await session.flush()

    response = await client.get(
        "/v1/calendar/corporate-actions",
        params={"event_types": "DIVIDEND_EX_DATE"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["event_type"] == "DIVIDEND_EX_DATE"


@pytest.mark.asyncio
async def test_list_calendar_events_empty(client):
    """Test listing all calendar events when DB is empty."""
    response = await client.get("/v1/calendar/events")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_calendar_events_date_range(client, session):
    """Test listing calendar events with date range filter."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Date Range Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for month in [1, 3, 5, 7, 9, 11]:
        session.add(CalendarEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            event_type="EARNINGS_ANNOUNCEMENT",
            event_date=date(2026, month, 15),
        ))
    await session.flush()

    response = await client.get(
        "/v1/calendar/events",
        params={"date_from": "2026-04-01", "date_to": "2026-10-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3  # May, July, September


@pytest.mark.asyncio
async def test_list_calendar_events_by_entity(client, session):
    """Test listing calendar events filtered by entity_ids."""
    entity_id = uuid.uuid4()
    other_entity_id = uuid.uuid4()
    for eid, name in [(entity_id, "Entity A"), (other_entity_id, "Entity B")]:
        session.add(Entity(
            entity_id=eid,
            entity_type="PUBLIC_COMPANY",
            legal_name=name,
            status="ACTIVE",
            source="SEC_EDGAR",
        ))
    await session.flush()

    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        event_type="SHAREHOLDER_MEETING",
        event_date=date(2026, 5, 1),
    ))
    session.add(CalendarEvent(
        event_id=uuid.uuid4(),
        entity_id=other_entity_id,
        event_type="SHAREHOLDER_MEETING",
        event_date=date(2026, 5, 2),
    ))
    await session.flush()

    response = await client.get(
        "/v1/calendar/events",
        params={"entity_ids": str(entity_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["entity_id"] == str(entity_id)
