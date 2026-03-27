"""API tests for Alert Expansion endpoints (Pillar 3 Phase 3C)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.fi_intelligence import (
    CrossAssetSignal,
    FIMarketBriefing,
    NewIssuanceEvent,
)
from src.models.alert_expansion import FIAlertConfig


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession) -> Entity:
    eid = uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Alert Expansion API Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_briefing_with_fallen_angels(session: AsyncSession) -> FIMarketBriefing:
    bid = uuid.uuid4()
    briefing = FIMarketBriefing(
        id=bid,
        briefing_date=date.today(),
        briefing_type="CREDIT",
        ig_oas_bps=Decimal("100.00"),
        hy_oas_bps=Decimal("400.00"),
        ig_oas_1w_change=Decimal("-8.00"),
        hy_oas_1w_change=Decimal("15.00"),
        credit_regime="WIDENING",
        fallen_angels_this_period={
            "entity_name": "FallenCorp",
            "agency": "S&P",
            "old_rating": "BBB-",
            "new_rating": "BB+",
            "spread_impact_bps": 45.0,
        },
    )
    session.add(briefing)
    await session.flush()
    return briefing


async def _seed_briefing_with_rising_stars(session: AsyncSession) -> FIMarketBriefing:
    bid = uuid.uuid4()
    briefing = FIMarketBriefing(
        id=bid,
        briefing_date=date.today(),
        briefing_type="CREDIT",
        ig_oas_bps=Decimal("90.00"),
        hy_oas_bps=Decimal("340.00"),
        ig_oas_1w_change=Decimal("3.00"),
        credit_regime="TIGHTENING",
        rising_stars_this_period={
            "entity_name": "StarCorp",
            "agency": "Moody's",
            "old_rating": "Ba1",
            "new_rating": "Baa3",
        },
    )
    session.add(briefing)
    await session.flush()
    return briefing


async def _seed_issuance_with_rating(session: AsyncSession) -> NewIssuanceEvent:
    iid = uuid.uuid4()
    event = NewIssuanceEvent(
        id=iid,
        issue_date=date.today(),
        rating="A-",
        size_mm=Decimal("500.00"),
    )
    session.add(event)
    await session.flush()
    return event


async def _seed_divergence_signal(session: AsyncSession) -> CrossAssetSignal:
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    signal = CrossAssetSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date.today(),
        signal_type="DIVERGENCE",
        spread_change_bps=Decimal("-20.00"),
        severity="HIGH",
    )
    session.add(signal)
    await session.flush()
    return signal


async def _seed_quality_alert_config(session: AsyncSession) -> FIAlertConfig:
    aid = uuid.uuid4()
    config = FIAlertConfig(
        id=aid,
        user_id="test-user",
        alert_type="QUALITY_SCORE",
        threshold_value=Decimal("75.00"),
        entity_scope={"entity_id": str(uuid.uuid4())},
    )
    session.add(config)
    await session.flush()
    return config


async def _seed_flow_alert_config(session: AsyncSession) -> FIAlertConfig:
    aid = uuid.uuid4()
    config = FIAlertConfig(
        id=aid,
        user_id="test-user",
        alert_type="INSTITUTIONAL_FLOW",
        threshold_value=Decimal("100.00"),
        entity_scope={"entity_id": str(uuid.uuid4())},
    )
    session.add(config)
    await session.flush()
    return config


# ══════════════════════════════════════════════════════════════════════
# FI Rating Changes
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fi_rating_changes_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/ratings returns 200 with empty list."""
    resp = await client.get("/v3/alerts/fi/ratings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_fi_rating_changes_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/ratings returns seeded rating data."""
    await _seed_issuance_with_rating(session)
    resp = await client.get("/v3/alerts/fi/ratings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["new_rating"] == "A-"


# ══════════════════════════════════════════════════════════════════════
# Fallen Angels
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fallen_angels_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/fallen-angels returns 200 empty."""
    resp = await client.get("/v3/alerts/fi/fallen-angels")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_fallen_angels_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/fallen-angels returns fallen angel events."""
    await _seed_briefing_with_fallen_angels(session)
    resp = await client.get("/v3/alerts/fi/fallen-angels")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entity_name"] == "FallenCorp"


# ══════════════════════════════════════════════════════════════════════
# Rising Stars
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_rising_stars_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/rising-stars returns 200 empty."""
    resp = await client.get("/v3/alerts/fi/rising-stars")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_rising_stars_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/rising-stars returns rising star events."""
    await _seed_briefing_with_rising_stars(session)
    resp = await client.get("/v3/alerts/fi/rising-stars")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["is_rising_star"] is True


# ══════════════════════════════════════════════════════════════════════
# Spread Moves
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_spread_moves_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/spread-moves returns 200 empty."""
    resp = await client.get("/v3/alerts/fi/spread-moves")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_spread_moves_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/spread-moves returns spread move alerts."""
    await _seed_briefing_with_fallen_angels(session)
    resp = await client.get("/v3/alerts/fi/spread-moves")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "severity" in data[0]


# ══════════════════════════════════════════════════════════════════════
# Regime & Divergence
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_regime_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/regime returns 200 empty."""
    resp = await client.get("/v3/alerts/fi/regime")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_regime_alerts_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/regime returns regime status."""
    await _seed_briefing_with_fallen_angels(session)
    resp = await client.get("/v3/alerts/fi/regime")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_divergence_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/divergence returns 200 empty."""
    resp = await client.get("/v3/alerts/fi/divergence")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_divergence_alerts_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/fi/divergence returns divergence signals."""
    await _seed_divergence_signal(session)
    resp = await client.get("/v3/alerts/fi/divergence")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["severity"] == "HIGH"


# ══════════════════════════════════════════════════════════════════════
# Quality Score & Institutional Flow Alerts
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_quality_score_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/quality-scores returns 200 empty."""
    resp = await client.get("/v3/alerts/quality-scores")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_quality_score_alerts_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/quality-scores returns quality alert events."""
    await _seed_quality_alert_config(session)
    resp = await client.get("/v3/alerts/quality-scores")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["alert_type"] == "QUALITY_SCORE"


@pytest.mark.asyncio
async def test_institutional_flow_alerts_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/institutional-flow returns 200 empty."""
    resp = await client.get("/v3/alerts/institutional-flow")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_institutional_flow_alerts_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/alerts/institutional-flow returns flow alerts."""
    await _seed_flow_alert_config(session)
    resp = await client.get("/v3/alerts/institutional-flow")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["alert_type"] == "INSTITUTIONAL_FLOW"
