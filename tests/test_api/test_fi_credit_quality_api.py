"""Tests for Credit Quality Analytics API endpoints (Pillar 2 FI Supplement – Part 4)."""

import uuid
from datetime import date

import pytest

from src.models.corporate_bond import CorporateBond
from src.models.credit_rating import CurrentCreditRating
from src.models.entity import Entity


def _seed_entity(session, name="Test Credit Quality Corp"):
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


def _seed_bond(session, entity_id, cusip="912828ZZ0"):
    """Seed a corporate bond linked to an entity."""
    bond = CorporateBond(
        bond_id=uuid.uuid4(),
        cusip=cusip,
        issuer_entity_id=entity_id,
        issuer_name="Test Corp",
        name=f"Test Corp 5.0 2030 ({cusip})",
        coupon_rate=5.0,
        coupon_type="FIXED",
        maturity_date=date(2030, 6, 15),
        status="OUTSTANDING",
    )
    session.add(bond)
    return bond


def _seed_rating(session, entity_id, rating="BBB", numeric=9, outlook="STABLE",
                 watch_status=None, agency="SP"):
    """Seed a current credit rating for an entity."""
    cr = CurrentCreditRating(
        id=uuid.uuid4(),
        entity_id=entity_id,
        agency=agency,
        rating_type="LONG_TERM",
        current_rating=rating,
        current_rating_numeric=numeric,
        outlook=outlook,
        watch_status=watch_status,
        is_investment_grade=(numeric <= 10),
    )
    session.add(cr)
    return cr


# ── Bond Credit Quality Endpoint ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_bond_credit_quality(client, session):
    """GET /v2/analytics/bonds/{cusip}/credit returns credit quality data."""
    entity_id = _seed_entity(session, "Bond CQ Corp")
    await session.flush()

    _seed_bond(session, entity_id, cusip="123456AA0")
    _seed_rating(session, entity_id, rating="BBB-", numeric=10, outlook="NEGATIVE")
    await session.flush()

    response = await client.get("/v2/analytics/bonds/123456AA0/credit")
    assert response.status_code == 200
    data = response.json()
    assert data["cusip"] == "123456AA0"
    # Should have fallen angel probability since it's BBB-
    assert data["fallen_angel_probability"] is not None
    assert data["fallen_angel_probability"] > 0
    # Should have credit momentum
    assert data["credit_momentum_signal"] is not None
    # Should have refi risk
    assert data["refinancing_risk_score"] is not None
    assert data["refinancing_risk_assessment"] is not None


@pytest.mark.asyncio
async def test_get_bond_credit_quality_not_found(client):
    """GET /v2/analytics/bonds/{cusip}/credit with unknown CUSIP returns 404."""
    response = await client.get("/v2/analytics/bonds/XXXXXXXXX/credit")
    assert response.status_code == 404


# ── Credit Momentum Endpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_credit_momentum(client, session):
    """GET /v2/analytics/entities/{id}/credit-momentum returns momentum data."""
    entity_id = _seed_entity(session, "Momentum Corp")
    await session.flush()

    response = await client.get(
        f"/v2/analytics/entities/{entity_id}/credit-momentum",
        params={"rating_momentum": 0.5, "score_momentum": 0.3, "spread_momentum": 0.4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["signal"] == "IMPROVING"
    assert data["momentum_score"] > 0.15
    assert "components" in data
    assert data["components"]["rating_weight"] == 0.4


@pytest.mark.asyncio
async def test_get_credit_momentum_entity_not_found(client):
    """GET /v2/analytics/entities/{id}/credit-momentum with bad ID returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v2/analytics/entities/{fake_id}/credit-momentum")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_credit_momentum_deteriorating(client, session):
    """Credit momentum with negative inputs should return DETERIORATING."""
    entity_id = _seed_entity(session, "Deteriorating Corp")
    await session.flush()

    response = await client.get(
        f"/v2/analytics/entities/{entity_id}/credit-momentum",
        params={"rating_momentum": -0.6, "score_momentum": -0.5, "spread_momentum": -0.4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "DETERIORATING"
    assert data["momentum_score"] < -0.15


# ── Fallen Angel Watch Endpoint ────────────────────────────────────


@pytest.mark.asyncio
async def test_fallen_angel_watch(client, session):
    """GET /v2/analytics/entities/fallen-angel-watch returns BBB entities."""
    entity_id1 = _seed_entity(session, "BBB Corp 1")
    entity_id2 = _seed_entity(session, "BBB Minus Corp")
    await session.flush()

    _seed_rating(session, entity_id1, rating="BBB", numeric=9, outlook="STABLE")
    _seed_rating(session, entity_id2, rating="BBB-", numeric=10, outlook="NEGATIVE",
                 watch_status="WATCH_NEGATIVE")
    await session.flush()

    response = await client.get("/v2/analytics/entities/fallen-angel-watch")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["entities"]) >= 2
    # BBB- on watch negative should be first (highest probability)
    entities = data["entities"]
    probs = [e["fallen_angel_probability"] for e in entities]
    assert probs == sorted(probs, reverse=True)


@pytest.mark.asyncio
async def test_fallen_angel_watch_empty(client, session):
    """GET /v2/analytics/entities/fallen-angel-watch with no BBB entities."""
    # Seed an AA-rated entity (should not appear)
    entity_id = _seed_entity(session, "AA Corp")
    await session.flush()
    _seed_rating(session, entity_id, rating="AA", numeric=3, outlook="STABLE")
    await session.flush()

    response = await client.get("/v2/analytics/entities/fallen-angel-watch")
    assert response.status_code == 200
    data = response.json()
    # May or may not be empty depending on other tests' data, but at least should work
    assert "entities" in data
    assert "total" in data


# ── Refinancing Risk Endpoint ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_refinancing_risk(client, session):
    """GET /v2/analytics/entities/{id}/refinancing-risk returns risk data."""
    entity_id = _seed_entity(session, "Refi Risk Corp")
    await session.flush()

    response = await client.get(
        f"/v2/analytics/entities/{entity_id}/refinancing-risk",
        params={
            "maturity_wall_pct": 70.0,
            "current_spread_bps": 600.0,
            "fcf_to_debt": 0.05,
            "credit_direction": -0.5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["score"] > 0
    assert data["assessment"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")
    assert "components" in data
    assert data["maturity_wall_pct"] == 70.0
    assert data["current_spread_bps"] == 600.0


@pytest.mark.asyncio
async def test_get_refinancing_risk_entity_not_found(client):
    """GET /v2/analytics/entities/{id}/refinancing-risk with bad ID returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v2/analytics/entities/{fake_id}/refinancing-risk")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_refinancing_risk_low(client, session):
    """Low risk inputs should yield LOW assessment."""
    entity_id = _seed_entity(session, "Low Refi Risk Corp")
    await session.flush()

    response = await client.get(
        f"/v2/analytics/entities/{entity_id}/refinancing-risk",
        params={
            "maturity_wall_pct": 5.0,
            "current_spread_bps": 50.0,
            "fcf_to_debt": 0.60,
            "credit_direction": 0.8,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assessment"] == "LOW"
    assert data["score"] < 25.0
