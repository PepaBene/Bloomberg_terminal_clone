"""Tests for credit rating event models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.credit_rating import CreditRatingEvent
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_credit_rating_event(session):
    """Test creating a credit rating event."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Rated Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    event_id = uuid.uuid4()
    event = CreditRatingEvent(
        event_id=event_id,
        entity_id=entity_id,
        agency="SP",
        rating_type="LONG_TERM",
        new_rating="BBB+",
        old_rating="BBB",
        direction="UPGRADE",
        outlook="STABLE",
        event_date=date(2026, 1, 15),
        source_type="8K_FILING",
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event_id)
    )
    fetched = result.scalar_one()
    assert fetched.agency == "SP"
    assert fetched.new_rating == "BBB+"
    assert fetched.old_rating == "BBB"
    assert fetched.direction == "UPGRADE"
    assert fetched.outlook == "STABLE"


@pytest.mark.asyncio
async def test_list_ratings_by_entity(session):
    """Test querying credit rating events by entity."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Multi-Rated Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for i, (agency, rating) in enumerate([("SP", "A-"), ("MOODYS", "A3"), ("FITCH", "A-")]):
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency=agency,
            new_rating=rating,
            direction="AFFIRM",
            event_date=date(2026, 1 + i, 10),
        ))
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.entity_id == entity_id)
    )
    events = result.scalars().all()
    assert len(events) == 3
    agencies = {e.agency for e in events}
    assert agencies == {"SP", "MOODYS", "FITCH"}


@pytest.mark.asyncio
async def test_filter_ratings_by_agency(session):
    """Test filtering credit rating events by agency."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Filter Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="SP",
        new_rating="BBB",
        direction="DOWNGRADE",
        event_date=date(2026, 2, 1),
    ))
    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="MOODYS",
        new_rating="Baa2",
        direction="DOWNGRADE",
        event_date=date(2026, 2, 5),
    ))
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent)
        .where(CreditRatingEvent.entity_id == entity_id)
        .where(CreditRatingEvent.agency == "SP")
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].new_rating == "BBB"
