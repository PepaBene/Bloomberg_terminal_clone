"""Tests for Fixed Income - Bond Issuances API endpoints (D11 FI Supplement P7)."""

import uuid
from datetime import date

import pytest

from src.models.bond_issuance import BondIssuance
from src.models.entity import Entity


async def _seed_entity(session):
    """Helper to seed an issuer entity."""
    entity = Entity(
        entity_type="PUBLIC_COMPANY",
        legal_name="Test Corp",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_issuance(session, entity, pricing_date, **kwargs):
    """Helper to seed a bond issuance."""
    issuance = BondIssuance(
        issuer_entity_id=entity.entity_id,
        pricing_date=pricing_date,
        **kwargs,
    )
    session.add(issuance)
    await session.flush()
    return issuance


@pytest.mark.asyncio
async def test_list_issuances(client, session):
    """Seed 2 issuances, GET /v1/fixed-income/issuances -> 200, count=2."""
    entity = await _seed_entity(session)
    await _seed_issuance(
        session, entity, date(2025, 6, 15),
        coupon_rate=5.25, maturity_date=date(2035, 6, 15),
        issued_size_mm=1000.0, currency="USD",
        lead_left_bookrunner="Goldman Sachs",
    )
    await _seed_issuance(
        session, entity, date(2025, 7, 15),
        coupon_rate=4.75, maturity_date=date(2030, 7, 15),
        issued_size_mm=750.0, currency="USD",
        lead_left_bookrunner="JP Morgan",
    )

    response = await client.get("/v1/fixed-income/issuances")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_get_issuance(client, session):
    """Seed 1, GET /v1/fixed-income/issuances/{id} -> 200."""
    entity = await _seed_entity(session)
    issuance = await _seed_issuance(
        session, entity, date(2025, 8, 1),
        coupon_rate=5.0, maturity_date=date(2035, 8, 1),
        issued_size_mm=500.0, currency="USD",
        seniority="SENIOR_UNSECURED",
    )

    response = await client.get(f"/v1/fixed-income/issuances/{issuance.issuance_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["issuance_id"] == str(issuance.issuance_id)
    assert data["seniority"] == "SENIOR_UNSECURED"


@pytest.mark.asyncio
async def test_get_issuance_404(client):
    """GET with random UUID -> 404."""
    random_id = uuid.uuid4()
    response = await client.get(f"/v1/fixed-income/issuances/{random_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_issuer_issuances(client, session):
    """GET /v1/fixed-income/issuances/by-issuer/{entity_id} returns correct issuances."""
    entity = await _seed_entity(session)
    await _seed_issuance(
        session, entity, date(2025, 5, 1),
        issued_size_mm=600.0, currency="USD",
    )
    await _seed_issuance(
        session, entity, date(2025, 6, 1),
        issued_size_mm=800.0, currency="USD",
    )

    response = await client.get(f"/v1/fixed-income/issuances/by-issuer/{entity.entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
    for item in data["data"]:
        assert item["issuer_entity_id"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_volume_stats(client, session):
    """GET /v1/fixed-income/issuances/volume returns aggregated data."""
    entity = await _seed_entity(session)
    await _seed_issuance(
        session, entity, date(2025, 3, 10),
        issued_size_mm=500.0, currency="USD",
    )
    await _seed_issuance(
        session, entity, date(2025, 3, 20),
        issued_size_mm=750.0, currency="USD",
    )

    response = await client.get("/v1/fixed-income/issuances/volume", params={"period": "monthly"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    entry = data[0]
    assert "period" in entry
    assert "count" in entry
    assert "total_volume_mm" in entry
    assert "avg_size_mm" in entry


@pytest.mark.asyncio
async def test_league_tables(client, session):
    """GET /v1/fixed-income/issuances/league-tables returns bookrunner rankings."""
    entity = await _seed_entity(session)
    await _seed_issuance(
        session, entity, date(2025, 4, 1),
        issued_size_mm=1000.0, currency="USD",
        lead_left_bookrunner="Goldman Sachs",
    )
    await _seed_issuance(
        session, entity, date(2025, 4, 15),
        issued_size_mm=800.0, currency="USD",
        lead_left_bookrunner="JP Morgan",
    )

    response = await client.get("/v1/fixed-income/issuances/league-tables")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    assert data[0]["rank"] == 1
    assert "bookrunner" in data[0]
    assert "deal_count" in data[0]
    assert "total_volume_mm" in data[0]
    assert "market_share_pct" in data[0]
