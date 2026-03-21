"""Tests for Executives API endpoints."""

import uuid

import pytest

from src.models.entity import Entity
from src.models.executives import Executive, ExecutiveRole


@pytest.mark.asyncio
async def test_list_entity_executives_empty(client):
    """Test listing executives for an entity when DB is empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/executives")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_entity_executives(client, session):
    """Test listing executives for an entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Exec Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    for name, title in [("Alice Smith", "CEO"), ("Bob Jones", "CFO")]:
        exec_id = uuid.uuid4()
        session.add(Executive(executive_id=exec_id, person_name=name))
        await session.flush()
        session.add(ExecutiveRole(
            role_id=uuid.uuid4(), executive_id=exec_id,
            entity_id=entity_id, title=title, role_type="EXECUTIVE",
        ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/executives")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_search_executives_empty(client):
    """Test searching executives when DB is empty."""
    response = await client.get("/v1/executives/search")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_search_executives_by_name(client, session):
    """Test searching executives by name."""
    session.add(Executive(executive_id=uuid.uuid4(), person_name="Tim Cook"))
    session.add(Executive(executive_id=uuid.uuid4(), person_name="Satya Nadella"))
    session.add(Executive(executive_id=uuid.uuid4(), person_name="Tim Apple"))
    await session.flush()

    response = await client.get("/v1/executives/search", params={"name": "Tim"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_search_executives_case_insensitive(client, session):
    """Test that name search is case-insensitive."""
    session.add(Executive(executive_id=uuid.uuid4(), person_name="Satya Nadella"))
    await session.flush()

    response = await client.get("/v1/executives/search", params={"name": "satya"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
