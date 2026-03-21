"""API tests for company primer endpoints (Pillar 2 Supplement – Part 7)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity


async def _seed_entity(session: AsyncSession) -> uuid.UUID:
    """Seed a test entity and return its ID."""
    eid = uuid.uuid4()
    session.add(Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Primer Test Corp",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    ))
    await session.commit()
    return eid


@pytest.mark.asyncio
async def test_get_primer(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/primer/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["ai_enabled"] is False
    assert data["business_description"] is None
    assert data["financial_summary"] is not None
    assert data["valuation_summary"] is not None


@pytest.mark.asyncio
async def test_get_primer_entity_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/analytics/primer/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_financials(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/primer/{eid}/financials")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert "financial_summary" in data
    assert "valuation_summary" in data


@pytest.mark.asyncio
async def test_primer_ai_disabled(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/primer/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is False
    assert data["competitive_position"] is None
