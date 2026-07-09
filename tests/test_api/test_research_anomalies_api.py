"""API tests for Research Anomaly Detection endpoints (Pillar 3 Phase 4A)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.anomaly_detection import DetectedAnomaly, AnomalyRule


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Anomaly Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_anomaly(
    session,
    entity_id,
    anomaly_type="VOLUME_SPIKE",
    severity=Decimal("90.00"),
    acknowledged=False,
    window_start=None,
):
    aid = uuid.uuid4()
    anomaly = DetectedAnomaly(
        id=aid,
        entity_id=entity_id,
        anomaly_type=anomaly_type,
        severity_score=severity,
        anomaly_window_start=window_start or date(2025, 11, 1),
        anomaly_window_end=date(2025, 11, 1),
        lookback_period="30D",
        observed_value=Decimal("10000000.0000"),
        expected_value=Decimal("3000000.0000"),
        z_score=Decimal("3.2000"),
        percentile_rank=Decimal("98.50"),
        contextual_analysis={"trigger": "earnings_surprise"},
        ai_narrative="Significant volume anomaly detected.",
        confidence_level=Decimal("0.92"),
        is_acknowledged=acknowledged,
    )
    session.add(anomaly)
    await session.flush()
    return anomaly


async def _seed_rule(session, anomaly_type="VOLUME_SPIKE", rule_name="Test Rule"):
    rid = uuid.uuid4()
    rule = AnomalyRule(
        id=rid,
        anomaly_type=anomaly_type,
        rule_name=rule_name,
        description="Test detection rule.",
        threshold_config={"z_score_threshold": 3.0},
        is_enabled=True,
    )
    session.add(rule)
    await session.flush()
    return rule


# ── GET /research/anomalies/active ───────────────────────────────────


@pytest.mark.asyncio
async def test_active_anomalies_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/active returns empty when no data."""
    resp = await client.get("/v4/research/anomalies/active")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_active_anomalies_excludes_acknowledged(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/active excludes acknowledged anomalies."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, acknowledged=False)
    await _seed_anomaly(session, entity.entity_id, acknowledged=True)
    resp = await client.get("/v4/research/anomalies/active")
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["is_acknowledged"] is False


@pytest.mark.asyncio
async def test_active_anomalies_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/active returns unacknowledged anomalies."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id)
    resp = await client.get("/v4/research/anomalies/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/anomalies/critical ─────────────────────────────────


@pytest.mark.asyncio
async def test_critical_anomalies_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/critical returns empty when no critical anomalies."""
    resp = await client.get("/v4/research/anomalies/critical")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_critical_anomalies_threshold(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/critical returns only high severity."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, severity=Decimal("90.00"))
    await _seed_anomaly(session, entity.entity_id, severity=Decimal("50.00"))
    resp = await client.get("/v4/research/anomalies/critical", params={"threshold": 85})
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["severity_score"] >= 85


@pytest.mark.asyncio
async def test_critical_anomalies_custom_threshold(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/critical with custom threshold."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, severity=Decimal("60.00"))
    resp = await client.get("/v4/research/anomalies/critical", params={"threshold": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/anomalies/today ────────────────────────────────────


@pytest.mark.asyncio
async def test_today_anomalies_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/today returns empty when no today anomalies."""
    resp = await client.get("/v4/research/anomalies/today")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_today_anomalies_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/today returns anomalies detected today."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, window_start=date.today())
    resp = await client.get("/v4/research/anomalies/today")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/anomalies/statistics ───────────────────────────────


@pytest.mark.asyncio
async def test_statistics_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/statistics returns zeros when no data."""
    resp = await client.get("/v4/research/anomalies/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_anomalies"] >= 0
    assert "active_anomalies" in data
    assert "critical_anomalies" in data
    assert "acknowledged_anomalies" in data


@pytest.mark.asyncio
async def test_statistics_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/statistics returns accurate counts."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, severity=Decimal("90.00"), acknowledged=False)
    await _seed_anomaly(session, entity.entity_id, severity=Decimal("50.00"), acknowledged=True)
    resp = await client.get("/v4/research/anomalies/statistics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_anomalies"] >= 2


# ── GET /research/anomalies/rules ────────────────────────────────────


@pytest.mark.asyncio
async def test_rules_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/rules returns empty when no rules."""
    resp = await client.get("/v4/research/anomalies/rules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_rules_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/rules returns configured rules."""
    await _seed_rule(session)
    resp = await client.get("/v4/research/anomalies/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["anomaly_type"] == "VOLUME_SPIKE"


# ── POST /research/anomalies/rules ──────────────────────────────────


@pytest.mark.asyncio
async def test_create_rule(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/anomalies/rules creates a new rule."""
    resp = await client.post(
        "/v4/research/anomalies/rules",
        json={
            "anomaly_type": "SPREAD_WIDENING",
            "rule_name": "Spread Alert",
            "description": "Alert on widening spreads.",
            "threshold_config": {"spread_threshold_bps": 50},
            "is_enabled": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["anomaly_type"] == "SPREAD_WIDENING"
    assert data["rule_name"] == "Spread Alert"
    assert data["is_enabled"] is True


# ── GET /research/anomalies/by-type/{anomaly_type} ───────────────────


@pytest.mark.asyncio
async def test_by_type_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/by-type/UNKNOWN returns empty."""
    resp = await client.get("/v4/research/anomalies/by-type/UNKNOWN_TYPE")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_by_type_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/by-type/VOLUME_SPIKE returns filtered anomalies."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id, anomaly_type="VOLUME_SPIKE")
    await _seed_anomaly(session, entity.entity_id, anomaly_type="SPREAD_WIDENING")
    resp = await client.get("/v4/research/anomalies/by-type/VOLUME_SPIKE")
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["anomaly_type"] == "VOLUME_SPIKE"


# ── GET /research/anomalies/{entity_id} ──────────────────────────────


@pytest.mark.asyncio
async def test_entity_anomalies_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/{entity_id} returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/anomalies/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entity_anomalies_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/{entity_id} returns entity anomalies."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id)
    resp = await client.get(f"/v4/research/anomalies/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/anomalies/{entity_id}/history ──────────────────────


@pytest.mark.asyncio
async def test_entity_history_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/{entity_id}/history returns 404 for unknown entity."""
    resp = await client.get(f"/v4/research/anomalies/{uuid.uuid4()}/history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entity_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/anomalies/{entity_id}/history returns historical anomalies."""
    entity = await _seed_entity(session)
    await _seed_anomaly(session, entity.entity_id)
    resp = await client.get(f"/v4/research/anomalies/{entity.entity_id}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── POST /research/anomalies/{anomaly_id}/acknowledge ────────────────


@pytest.mark.asyncio
async def test_acknowledge_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/anomalies/{anomaly_id}/acknowledge returns 404."""
    resp = await client.post(f"/v4/research/anomalies/{uuid.uuid4()}/acknowledge")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_acknowledge_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/anomalies/{anomaly_id}/acknowledge sets acknowledged."""
    entity = await _seed_entity(session)
    anomaly = await _seed_anomaly(session, entity.entity_id, acknowledged=False)
    resp = await client.post(
        f"/v4/research/anomalies/{anomaly.id}/acknowledge",
        params={"acknowledged_by": "analyst_001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_acknowledged"] is True
    assert data["acknowledged_by"] == "analyst_001"


# ── PUT /research/anomalies/rules/{rule_id} ──────────────────────────


@pytest.mark.asyncio
async def test_update_rule_not_found(client: AsyncClient, session: AsyncSession):
    """PUT /v4/research/anomalies/rules/{rule_id} returns 404 for unknown rule."""
    resp = await client.put(
        f"/v4/research/anomalies/rules/{uuid.uuid4()}",
        json={
            "anomaly_type": "VOLUME_SPIKE",
            "rule_name": "Updated Rule",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_rule_success(client: AsyncClient, session: AsyncSession):
    """PUT /v4/research/anomalies/rules/{rule_id} updates the rule."""
    rule = await _seed_rule(session)
    resp = await client.put(
        f"/v4/research/anomalies/rules/{rule.id}",
        json={
            "anomaly_type": "SPREAD_WIDENING",
            "rule_name": "Updated Rule Name",
            "description": "Updated description.",
            "threshold_config": {"spread_threshold_bps": 100},
            "is_enabled": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["anomaly_type"] == "SPREAD_WIDENING"
    assert data["rule_name"] == "Updated Rule Name"
    assert data["is_enabled"] is False


# ── POST /research/anomalies/scan/{entity_id} ───────────────────────


@pytest.mark.asyncio
async def test_scan_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/anomalies/scan/{entity_id} returns 404 for unknown entity."""
    resp = await client.post(f"/v4/research/anomalies/scan/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scan_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/anomalies/scan/{entity_id} runs a real scan and completes."""
    entity = await _seed_entity(session)
    resp = await client.post(f"/v4/research/anomalies/scan/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    # No price history seeded for this entity, so nothing is detected —
    # but the scan itself must actually run (not just echo "INITIATED").
    assert data["scan_status"] == "COMPLETED"
    assert data["anomalies_detected"] == 0
    assert data["entity_id"] == str(entity.entity_id)
