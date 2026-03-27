"""API tests for FI Cross-Asset Signals endpoints (Pillar 2 FI Supplement -- Part 7)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID, name: str = "E15 Test Corp") -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name=name,
        short_name="E15TEST",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_divergence_signals_equity_rally(client: AsyncClient):
    """GET /v2/analytics/cross-asset/divergence-signals detects equity rally + bond deterioration."""
    resp = await client.get(
        "/v2/analytics/cross-asset/divergence-signals",
        params={
            "return_3m": 0.20,
            "return_6m": 0.25,
            "spread_bps": 350.0,
            "spread_change_3m_bps": 80.0,
            "spread_percentile": 70.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    signal_types = [s["signal_type"] for s in data["signals"]]
    assert "EQUITY_RALLY_BOND_DETERIORATION" in signal_types


@pytest.mark.asyncio
async def test_get_divergence_signals_no_signals(client: AsyncClient):
    """GET /v2/analytics/cross-asset/divergence-signals returns empty when aligned."""
    resp = await client.get(
        "/v2/analytics/cross-asset/divergence-signals",
        params={
            "return_3m": 0.05,
            "return_6m": 0.08,
            "spread_bps": 150.0,
            "spread_change_3m_bps": -5.0,
            "spread_percentile": 40.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["signals"] == []


@pytest.mark.asyncio
async def test_get_entity_cross_asset_signals(client: AsyncClient, session: AsyncSession):
    """GET /v2/analytics/entities/{id}/cross-asset-signals returns entity-specific signals."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)

    resp = await client.get(
        f"/v2/analytics/entities/{eid}/cross-asset-signals",
        params={
            "return_3m": 0.01,
            "return_6m": 0.02,
            "spread_bps": 600.0,
            "spread_change_3m_bps": 220.0,
            "spread_percentile": 85.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # Entity info should be present on signals
    for sig in data["signals"]:
        assert sig["entity_id"] == str(eid)
        assert sig["entity_name"] == "E15 Test Corp"


@pytest.mark.asyncio
async def test_get_entity_cross_asset_signals_404(client: AsyncClient):
    """GET /v2/analytics/entities/{id}/cross-asset-signals returns 404 for missing entity."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v2/analytics/entities/{fake_id}/cross-asset-signals")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_regime_risk_on(client: AsyncClient):
    """GET /v2/analytics/cross-asset/regime returns RISK_ON for benign conditions."""
    resp = await client.get(
        "/v2/analytics/cross-asset/regime",
        params={
            "equity_vol": 0.10,
            "credit_spread": 150.0,
            "rate_level": 0.03,
            "curve_slope": 0.015,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["regime"] == "RISK_ON"
    assert "factors" in data
    assert data["factors"]["vol_signal"] == "RISK_ON"
    assert data["factors"]["credit_signal"] == "RISK_ON"


@pytest.mark.asyncio
async def test_get_regime_stress(client: AsyncClient):
    """GET /v2/analytics/cross-asset/regime returns STRESS for extreme conditions."""
    resp = await client.get(
        "/v2/analytics/cross-asset/regime",
        params={
            "equity_vol": 0.45,
            "credit_spread": 800.0,
            "rate_level": 0.06,
            "curve_slope": -0.02,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["regime"] == "STRESS"


@pytest.mark.asyncio
async def test_get_equity_exposure_stress(client: AsyncClient):
    """GET /v2/analytics/cross-asset/regime/equity-exposure suggests reduction in STRESS."""
    resp = await client.get(
        "/v2/analytics/cross-asset/regime/equity-exposure",
        params={
            "equity_vol": 0.40,
            "credit_spread": 700.0,
            "rate_level": 0.05,
            "curve_slope": -0.015,
            "current_equity_weight": 0.60,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["regime"] == "STRESS"
    assert data["current_weight"] == 0.60
    assert data["suggested_weight"] < 0.60
    assert data["adjustment_pct"] < 0
    assert len(data["reason"]) > 0


@pytest.mark.asyncio
async def test_get_equity_exposure_risk_on(client: AsyncClient):
    """GET /v2/analytics/cross-asset/regime/equity-exposure maintains in RISK_ON."""
    resp = await client.get(
        "/v2/analytics/cross-asset/regime/equity-exposure",
        params={
            "equity_vol": 0.10,
            "credit_spread": 100.0,
            "rate_level": 0.03,
            "curve_slope": 0.02,
            "current_equity_weight": 0.60,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["regime"] == "RISK_ON"
    assert data["suggested_weight"] >= 0.60
