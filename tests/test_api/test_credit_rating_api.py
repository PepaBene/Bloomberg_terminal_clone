"""Tests for Credit Rating History API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.credit_rating import CreditRatingEvent
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_list_credit_ratings_empty(client):
    """Test listing credit ratings when DB is empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/credit-ratings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_credit_ratings(client, session):
    """Test listing credit rating events for an entity."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Rated API Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for i, (agency, rating) in enumerate([("SP", "BBB+"), ("MOODYS", "Baa1")]):
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency=agency,
            new_rating=rating,
            direction="AFFIRM",
            event_date=date(2026, 1 + i, 10),
        ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/credit-ratings")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_list_credit_ratings_filter_agency(client, session):
    """Test filtering credit ratings by agency."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Filter API Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="SP",
        new_rating="A-",
        direction="UPGRADE",
        event_date=date(2026, 1, 15),
    ))
    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="FITCH",
        new_rating="A-",
        direction="UPGRADE",
        event_date=date(2026, 1, 20),
    ))
    await session.flush()

    response = await client.get(
        f"/v1/entities/{entity_id}/credit-ratings",
        params={"agency": "SP"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["agency"] == "SP"


@pytest.mark.asyncio
async def test_credit_rating_history_empty(client):
    """Test credit rating history when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/credit-ratings/history")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_credit_rating_history_date_range(client, session):
    """Test credit rating history with date range filters."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="History API Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for month in [1, 3, 6, 9]:
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency="SP",
            new_rating="BBB",
            direction="AFFIRM",
            event_date=date(2026, month, 15),
        ))
    await session.flush()

    response = await client.get(
        f"/v1/entities/{entity_id}/credit-ratings/history",
        params={"start": "2026-02-01", "end": "2026-07-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2  # March and June
