"""Tests for the Risk Analytics API endpoints (E5).

Covers VaR, stress testing, factor exposures, fundamental risk,
volatility, beta, and drawdown endpoints.
"""

import math
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.security import EODPrice, Security


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    d = start
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _make_prices(security_id: uuid.UUID, n: int = 260) -> list[EODPrice]:
    dates = _business_days(date(2025, 1, 2), n)
    rows: list[EODPrice] = []
    now = datetime.now(timezone.utc)
    for i, d in enumerate(dates):
        close = 100.0 + math.sin(i / 10.0) * 5.0 + i * 0.01
        rows.append(
            EODPrice(
                security_id=security_id,
                price_date=d,
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                close_adjusted=close,
                volume=1_000_000,
                source="TEST",
                created_at=now,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def risk_data(session: AsyncSession):
    now = datetime.now(timezone.utc)
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Risk API Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Risk API Corp Stock",
        short_name="RAPI",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add(security)
    await session.flush()

    prices = _make_prices(security.security_id, n=260)
    session.add_all(prices)
    await session.flush()

    return {
        "security_id": security.security_id,
        "entity_id": entity.entity_id,
    }


# ---------------------------------------------------------------------------
# VaR endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_var_200(client, risk_data):
    """GET /v2/analytics/risk/var/{id} returns 200 with VaR data."""
    resp = await client.get(f"/v2/analytics/risk/var/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert "historical_var" in data
    assert "95_1d" in data["historical_var"]


@pytest.mark.asyncio
async def test_var_404(client):
    """GET /v2/analytics/risk/var/{unknown} returns 404."""
    resp = await client.get(f"/v2/analytics/risk/var/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Stress scenarios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stress_scenarios_list(client):
    """GET /v2/analytics/risk/stress/scenarios returns scenario list."""
    resp = await client.get("/v2/analytics/risk/stress/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    names = [s["name"] for s in data]
    assert "GFC_2008" in names
    assert "EQUITY_MINUS_20" in names


@pytest.mark.asyncio
async def test_stress_run(client, risk_data):
    """POST /v2/analytics/risk/stress/run runs a stress test."""
    resp = await client.post("/v2/analytics/risk/stress/run", json={
        "security_id": str(risk_data["security_id"]),
        "scenario_name": "EQUITY_MINUS_20",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert len(data["scenarios"]) == 1
    assert data["scenarios"][0]["scenario_name"] == "EQUITY_MINUS_20"


# ---------------------------------------------------------------------------
# Factor exposures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factors_200(client, risk_data):
    """GET /v2/analytics/risk/factors/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/risk/factors/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert "factors" in data


@pytest.mark.asyncio
async def test_factors_404(client):
    """GET /v2/analytics/risk/factors/{unknown} returns 404."""
    resp = await client.get(f"/v2/analytics/risk/factors/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Fundamental risk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fundamental_risk_200(client, risk_data):
    """GET /v2/analytics/risk/fundamental/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/risk/fundamental/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert "leverage_risk" in data


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_volatility_200(client, risk_data):
    """GET /v2/analytics/risk/volatility/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/risk/volatility/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert data["annualized_volatility"] is not None
    assert data["annualized_volatility"] > 0


# ---------------------------------------------------------------------------
# Beta
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_beta_200(client, risk_data):
    """GET /v2/analytics/risk/beta/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/risk/beta/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert "benchmark" in data


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drawdown_200(client, risk_data):
    """GET /v2/analytics/risk/drawdown/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/risk/drawdown/{risk_data['security_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert data["max_drawdown"] is not None
    assert data["risk_level"] in ["HIGH", "MODERATE", "LOW", "UNKNOWN"]


# ---------------------------------------------------------------------------
# Leverage risk detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leverage_risk_200(client, risk_data):
    """GET /v2/analytics/risk/fundamental/{id}/leverage returns 200."""
    resp = await client.get(f"/v2/analytics/risk/fundamental/{risk_data['security_id']}/leverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])


# ---------------------------------------------------------------------------
# Liquidity risk detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_liquidity_risk_200(client, risk_data):
    """GET /v2/analytics/risk/fundamental/{id}/liquidity returns 200."""
    resp = await client.get(f"/v2/analytics/risk/fundamental/{risk_data['security_id']}/liquidity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(risk_data["security_id"])
    assert data["avg_volume_20d"] is not None
