"""Tests for Earnings Intelligence API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.earnings_intelligence import EarningsSurprise, GuidanceTracking
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_list_earnings_surprises_empty(client):
    """Test listing earnings surprises when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/earnings-surprises")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_earnings_surprises(client, session):
    """Test listing earnings surprises for an entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Surprise Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    for q in range(1, 5):
        session.add(EarningsSurprise(
            surprise_id=uuid.uuid4(),
            entity_id=entity_id,
            fiscal_year=2025,
            fiscal_quarter=q,
            actual_eps=2.0 + q * 0.1,
            consensus_eps=2.0,
            eps_surprise=q * 0.1,
        ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/earnings-surprises")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 4


@pytest.mark.asyncio
async def test_list_earnings_surprises_filter_year(client, session):
    """Test filtering surprises by fiscal year."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Year Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(EarningsSurprise(
        surprise_id=uuid.uuid4(), entity_id=entity_id,
        fiscal_year=2025, fiscal_quarter=4, actual_eps=2.0,
    ))
    session.add(EarningsSurprise(
        surprise_id=uuid.uuid4(), entity_id=entity_id,
        fiscal_year=2026, fiscal_quarter=1, actual_eps=2.2,
    ))
    await session.flush()

    response = await client.get(
        f"/v1/entities/{entity_id}/earnings-surprises",
        params={"fiscal_year": 2026},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_list_guidance_empty(client):
    """Test listing guidance when empty."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/guidance-tracking")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_guidance(client, session):
    """Test listing guidance for an entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Guide Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(), entity_id=entity_id,
        guidance_fiscal_year=2026, metric="EPS",
        guidance_low=8.50, guidance_high=9.00, guidance_midpoint=8.75,
        guidance_date=date(2026, 1, 25), guidance_type="INITIAL",
    ))
    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(), entity_id=entity_id,
        guidance_fiscal_year=2026, metric="REVENUE",
        guidance_low=40000.0, guidance_high=42000.0, guidance_midpoint=41000.0,
        guidance_date=date(2026, 1, 25), guidance_type="INITIAL",
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/guidance-tracking")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_list_guidance_filter_metric(client, session):
    """Test filtering guidance by metric."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Metric Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(), entity_id=entity_id,
        guidance_fiscal_year=2026, metric="EPS",
        guidance_midpoint=8.75, guidance_date=date(2026, 1, 25),
    ))
    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(), entity_id=entity_id,
        guidance_fiscal_year=2026, metric="REVENUE",
        guidance_midpoint=41000.0, guidance_date=date(2026, 1, 25),
    ))
    await session.flush()

    response = await client.get(
        f"/v1/entities/{entity_id}/guidance-tracking",
        params={"metric": "EPS"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["metric"] == "EPS"
