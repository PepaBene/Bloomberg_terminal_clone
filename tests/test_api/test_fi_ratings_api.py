"""Tests for Fixed Income Credit Ratings API endpoints (D11 FI Supplement P5)."""

import uuid
from datetime import date

import pytest

from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating
from src.models.entity import Entity


def _seed_entity(session, name="Test Corp FI"):
    """Seed a test entity and return its id."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name=name,
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    return entity_id


@pytest.mark.asyncio
async def test_get_current_ratings(client, session):
    """GET /fixed-income/ratings/entity/{id} returns current ratings."""
    entity_id = _seed_entity(session, "Current Ratings Corp")
    await session.flush()

    for agency, rating, numeric in [("SP", "BBB+", 8), ("MOODYS", "Baa1", 8)]:
        session.add(CurrentCreditRating(
            id=uuid.uuid4(),
            entity_id=entity_id,
            agency=agency,
            rating_type="LONG_TERM",
            current_rating=rating,
            current_rating_numeric=numeric,
            outlook="STABLE",
            is_investment_grade=True,
        ))
    await session.flush()

    response = await client.get(f"/v1/fixed-income/ratings/entity/{entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    agencies = {r["agency"] for r in data}
    assert agencies == {"SP", "MOODYS"}


@pytest.mark.asyncio
async def test_get_rating_history(client, session):
    """GET /fixed-income/ratings/entity/{id}/history returns event history."""
    entity_id = _seed_entity(session, "History Corp")
    await session.flush()

    for i in range(3):
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency="SP",
            new_rating="BBB",
            direction="AFFIRM",
            event_date=date(2026, 1 + i, 15),
            is_fallen_angel=False,
            is_rising_star=False,
        ))
    await session.flush()

    response = await client.get(f"/v1/fixed-income/ratings/entity/{entity_id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_fallen_angels(client, session):
    """GET /fixed-income/ratings/fallen-angels returns fallen angel events."""
    entity_id = _seed_entity(session, "Fallen Angel Corp")
    await session.flush()

    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="SP",
        old_rating="BBB-",
        new_rating="BB+",
        direction="DOWNGRADE",
        event_date=date(2026, 2, 1),
        old_rating_numeric=10,
        new_rating_numeric=11,
        notches_changed=-1,
        is_fallen_angel=True,
        is_rising_star=False,
    ))
    await session.flush()

    response = await client.get("/v1/fixed-income/ratings/fallen-angels")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] >= 1
    event_ids = [e["event_id"] for e in data["data"]]
    # The seeded fallen angel should appear
    fa_events = [e for e in data["data"] if e["old_rating"] == "BBB-" and e["new_rating"] == "BB+"]
    assert len(fa_events) >= 1


@pytest.mark.asyncio
async def test_rising_stars(client, session):
    """GET /fixed-income/ratings/rising-stars returns rising star events."""
    entity_id = _seed_entity(session, "Rising Star Corp")
    await session.flush()

    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="MOODYS",
        old_rating="Ba1",
        new_rating="Baa3",
        direction="UPGRADE",
        event_date=date(2026, 2, 10),
        old_rating_numeric=11,
        new_rating_numeric=10,
        notches_changed=1,
        is_fallen_angel=False,
        is_rising_star=True,
    ))
    await session.flush()

    response = await client.get("/v1/fixed-income/ratings/rising-stars")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] >= 1
    rs_events = [e for e in data["data"] if e["old_rating"] == "Ba1" and e["new_rating"] == "Baa3"]
    assert len(rs_events) >= 1


@pytest.mark.asyncio
async def test_recent_actions(client, session):
    """GET /fixed-income/ratings/recent?days=365 returns all seeded events."""
    entity_id = _seed_entity(session, "Recent Actions Corp")
    await session.flush()

    for i in range(2):
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency="SP",
            new_rating="A-",
            direction="AFFIRM",
            event_date=date(2026, 1 + i, 5),
            is_fallen_angel=False,
            is_rising_star=False,
        ))
    await session.flush()

    response = await client.get("/v1/fixed-income/ratings/recent", params={"days": 365})
    assert response.status_code == 200
    data = response.json()
    # At least 2 events (may include events from other tests in same module)
    assert data["meta"]["total_count"] >= 2


@pytest.mark.asyncio
async def test_filter_by_agency(client, session):
    """GET /fixed-income/ratings/recent?agency=SP returns only SP events."""
    entity_id = _seed_entity(session, "Agency Filter Corp")
    await session.flush()

    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="SP",
        new_rating="BBB+",
        direction="UPGRADE",
        event_date=date(2026, 3, 1),
        is_fallen_angel=False,
        is_rising_star=False,
    ))
    session.add(CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity_id,
        agency="FITCH",
        new_rating="BBB+",
        direction="UPGRADE",
        event_date=date(2026, 3, 2),
        is_fallen_angel=False,
        is_rising_star=False,
    ))
    await session.flush()

    response = await client.get(
        "/v1/fixed-income/ratings/recent",
        params={"days": 365, "agency": "SP"},
    )
    assert response.status_code == 200
    data = response.json()
    for event in data["data"]:
        assert event["agency"] == "SP"


@pytest.mark.asyncio
async def test_migration_matrix(client, session):
    """GET /fixed-income/ratings/migration-matrix returns a transition matrix."""
    entity_id = _seed_entity(session, "Migration Matrix Corp")
    await session.flush()

    transitions = [
        ("BBB", "BBB+"),
        ("BBB", "BBB-"),
        ("A-", "BBB+"),
    ]
    for old_r, new_r in transitions:
        session.add(CreditRatingEvent(
            event_id=uuid.uuid4(),
            entity_id=entity_id,
            agency="SP",
            old_rating=old_r,
            new_rating=new_r,
            direction="DOWNGRADE" if old_r < new_r else "UPGRADE",
            event_date=date(2026, 1, 15),
            is_fallen_angel=False,
            is_rising_star=False,
        ))
    await session.flush()

    response = await client.get("/v1/fixed-income/ratings/migration-matrix")
    assert response.status_code == 200
    data = response.json()
    assert "matrix" in data
    assert data["total_transitions"] >= 3
    # Check our specific transitions are present
    assert data["matrix"].get("BBB", {}).get("BBB+", 0) >= 1


@pytest.mark.asyncio
async def test_entity_not_found(client):
    """GET /fixed-income/ratings/entity/{random_uuid} returns 404."""
    random_id = uuid.uuid4()
    response = await client.get(f"/v1/fixed-income/ratings/entity/{random_id}")
    assert response.status_code == 404
