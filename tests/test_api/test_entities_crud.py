"""Tests for entity API endpoints with seeded data.

These tests seed data via the shared ``session`` fixture (which is the
same session used by the API handlers through the dependency override),
then exercise the HTTP endpoints and verify the responses.
"""

import uuid

import pytest

from src.models.entity import Entity


def _make_entity(**overrides) -> Entity:
    """Create an Entity instance with sensible defaults."""
    defaults = dict(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Default Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        confidence_score=0.99,
    )
    defaults.update(overrides)
    return Entity(**defaults)


# ── List endpoint ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_entity(client, session):
    """Test that a seeded entity appears in the list endpoint."""
    entity_id = uuid.uuid4()
    entity = _make_entity(entity_id=entity_id, legal_name="Apple Inc.")
    session.add(entity)
    await session.flush()

    response = await client.get("/v1/entities")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] >= 1

    # Find our entity in the results
    entity_ids = [e["entity_id"] for e in data["data"]]
    assert str(entity_id) in entity_ids


@pytest.mark.asyncio
async def test_list_entities_pagination(client, session):
    """Test that pagination metadata is correct."""
    # Seed 3 entities
    for name in ["Alpha Corp", "Beta Corp", "Gamma Corp"]:
        session.add(_make_entity(legal_name=name))
    await session.flush()

    response = await client.get("/v1/entities", params={"page_size": 2, "page": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 2
    assert data["meta"]["total_count"] >= 3
    assert len(data["data"]) <= 2


@pytest.mark.asyncio
async def test_list_entities_filter_by_status(client, session):
    """Test filtering entities by status."""
    session.add(_make_entity(legal_name="Active Corp", status="ACTIVE"))
    session.add(_make_entity(legal_name="Inactive Corp", status="INACTIVE"))
    await session.flush()

    response = await client.get("/v1/entities", params={"status": "INACTIVE"})
    assert response.status_code == 200
    data = response.json()
    for entity in data["data"]:
        assert entity["status"] == "INACTIVE"


@pytest.mark.asyncio
async def test_list_entities_filter_by_country(client, session):
    """Test filtering entities by incorporation country."""
    session.add(_make_entity(legal_name="US Corp", incorporation_country="US"))
    session.add(_make_entity(legal_name="UK Corp", incorporation_country="GB"))
    await session.flush()

    response = await client.get("/v1/entities", params={"country": "GB"})
    assert response.status_code == 200
    data = response.json()
    for entity in data["data"]:
        assert entity["incorporation_country"] == "GB"


# ── Get by ID endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_by_id(client, session):
    """Test getting a specific entity by ID."""
    entity_id = uuid.uuid4()
    entity = _make_entity(
        entity_id=entity_id,
        legal_name="Microsoft Corp",
        entity_type="CORPORATION",
    )
    session.add(entity)
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["legal_name"] == "Microsoft Corp"
    assert data["entity_type"] == "CORPORATION"
    assert data["entity_id"] == str(entity_id)


@pytest.mark.asyncio
async def test_get_entity_not_found(client, session):
    """Test that requesting a nonexistent entity returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v1/entities/{fake_id}")
    assert response.status_code == 404


# ── Search endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_entities(client, session):
    """Test searching entities by name."""
    entity = _make_entity(legal_name="Unique Search Target Corp")
    session.add(entity)
    await session.flush()

    response = await client.get(
        "/v1/entities/search", params={"q": "Unique Search Target"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    names = [r["legal_name"] for r in data["results"]]
    assert "Unique Search Target Corp" in names


@pytest.mark.asyncio
async def test_search_entities_case_insensitive(client, session):
    """Test that search is case-insensitive (ILIKE)."""
    entity = _make_entity(legal_name="CaseTest International")
    session.add(entity)
    await session.flush()

    response = await client.get(
        "/v1/entities/search", params={"q": "casetest"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_search_entities_no_results(client, session):
    """Test searching for a term that matches nothing."""
    response = await client.get(
        "/v1/entities/search",
        params={"q": "ZZZNonexistentEntityZZZ"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_search_entities_filter_by_type(client, session):
    """Test that search respects entity_type filter."""
    session.add(
        _make_entity(legal_name="FilterType Corp", entity_type="CORPORATION")
    )
    session.add(
        _make_entity(legal_name="FilterType Fund", entity_type="FUND")
    )
    await session.flush()

    response = await client.get(
        "/v1/entities/search",
        params={"q": "FilterType", "entity_type": "FUND"},
    )
    assert response.status_code == 200
    data = response.json()
    for r in data["results"]:
        assert r["entity_type"] == "FUND"
