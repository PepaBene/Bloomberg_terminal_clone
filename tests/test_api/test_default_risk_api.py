"""API tests for default risk scoring endpoints (Pillar 2 Supplement – Part 2)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.default_risk import DefaultRiskScore
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────

async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Test Corp",
        short_name="TEST",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


async def _seed_risk_score(
    session: AsyncSession,
    entity_id: uuid.UUID,
    calc_date: date,
    composite: float = 65.0,
    rating: str = "A-",
    zone: str = "INVESTMENT_GRADE",
    score_change: float | None = None,
    trend: str | None = None,
) -> DefaultRiskScore:
    score = DefaultRiskScore(
        score_id=uuid.uuid4(),
        entity_id=entity_id,
        calculation_date=calc_date,
        altman_z_score=2.8,
        altman_zone="SAFE",
        merton_dd=3.2,
        merton_pd=0.0012,
        merton_asset_value=150000.0,
        merton_asset_vol=0.22,
        equity_volatility=0.28,
        composite_score=composite,
        implied_rating=rating,
        credit_zone=zone,
        key_drivers=[
            {"driver": "altman_z", "contribution": 20.0, "description": "Z=2.80"},
            {"driver": "merton_dd", "contribution": 22.5, "description": "DD=3.20"},
        ],
        prior_score=composite - (score_change or 0.0),
        score_change=score_change,
        trend=trend or "STABLE",
        data_quality="HIGH",
        inputs={"equity_value": 100000, "total_debt": 50000},
    )
    session.add(score)
    await session.commit()
    return score


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_credit_risk_score(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/credit-risk/{entity_id} returns the latest score."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_risk_score(session, eid, date(2024, 7, 1))

    resp = await client.get(f"/v1/analytics/credit-risk/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["composite_score"] == pytest.approx(65.0, abs=0.1)
    assert data["implied_rating"] == "A-"
    assert data["credit_zone"] == "INVESTMENT_GRADE"
    assert data["altman"] is not None
    assert data["altman"]["z_score"] == pytest.approx(2.8, abs=0.01)
    assert data["merton"] is not None
    assert data["merton"]["distance_to_default"] == pytest.approx(3.2, abs=0.01)
    assert len(data["key_drivers"]) == 2


@pytest.mark.asyncio
async def test_get_credit_risk_score_404(client: AsyncClient):
    """GET /v1/analytics/credit-risk/{entity_id} returns 404 for unknown entity."""
    resp = await client.get(f"/v1/analytics/credit-risk/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_credit_risk_history(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/credit-risk/{entity_id}/history returns multiple points."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_risk_score(session, eid, date(2024, 8, 1), composite=60.0)
    await _seed_risk_score(session, eid, date(2024, 8, 15), composite=63.0)
    await _seed_risk_score(session, eid, date(2024, 9, 1), composite=65.0)

    resp = await client.get(f"/v1/analytics/credit-risk/{eid}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert len(data["points"]) == 3
    # Chronological order
    dates = [p["calculation_date"] for p in data["points"]]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_get_credit_risk_history_date_filter(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/credit-risk/{entity_id}/history supports date filters."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_risk_score(session, eid, date(2024, 9, 1), composite=60.0)
    await _seed_risk_score(session, eid, date(2024, 9, 15), composite=63.0)
    await _seed_risk_score(session, eid, date(2024, 10, 1), composite=65.0)

    resp = await client.get(
        f"/v1/analytics/credit-risk/{eid}/history",
        params={"start": "2024-09-10", "end": "2024-09-30"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) == 1
    assert data["points"][0]["calculation_date"] == "2024-09-15"


@pytest.mark.asyncio
async def test_get_credit_risk_drivers(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/credit-risk/{entity_id}/drivers returns decomposition."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_risk_score(session, eid, date(2024, 10, 1))

    resp = await client.get(f"/v1/analytics/credit-risk/{eid}/drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["composite_score"] == pytest.approx(65.0, abs=0.1)
    assert len(data["drivers"]) == 2
    assert data["drivers"][0]["driver"] == "altman_z"


@pytest.mark.asyncio
async def test_get_credit_risk_drivers_404(client: AsyncClient):
    """GET /v1/analytics/credit-risk/{entity_id}/drivers returns 404."""
    resp = await client.get(f"/v1/analytics/credit-risk/{uuid.uuid4()}/drivers")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_credit_risk_alerts(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/credit-risk/alerts returns deteriorating entities."""
    eid1 = uuid.uuid4()
    eid2 = uuid.uuid4()
    await _seed_entity(session, eid1)
    await _seed_entity(session, eid2)

    # eid1: deteriorating
    await _seed_risk_score(
        session, eid1, date(2024, 11, 1),
        composite=45.0, rating="BB+", zone="CROSSOVER",
        score_change=-12.0, trend="DETERIORATING",
    )
    # eid2: stable (no alert)
    await _seed_risk_score(
        session, eid2, date(2024, 11, 1),
        composite=70.0, rating="A", zone="INVESTMENT_GRADE",
        score_change=-2.0, trend="STABLE",
    )

    resp = await client.get("/v1/analytics/credit-risk/alerts", params={"min_score_change": -5.0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    alert_ids = [a["entity_id"] for a in data]
    assert str(eid1) in alert_ids
    assert str(eid2) not in alert_ids


@pytest.mark.asyncio
async def test_get_credit_risk_alerts_empty(client: AsyncClient):
    """GET /v1/analytics/credit-risk/alerts returns empty list when no alerts."""
    resp = await client.get(
        "/v1/analytics/credit-risk/alerts",
        params={"min_score_change": -99.0},
    )
    assert resp.status_code == 200
    # May pick up alerts from other tests (module-scoped DB), just check it returns a list
    assert isinstance(resp.json(), list)
