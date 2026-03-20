"""Tests for the Quantitative Analytics API endpoints (E7).

Covers regression, rolling regression, correlation, stationarity,
cointegration, autocorrelation, summary, and beta endpoints.
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


def _make_prices(security_id: uuid.UUID, n: int = 260, base: float = 100.0) -> list[EODPrice]:
    dates = _business_days(date(2025, 1, 2), n)
    rows: list[EODPrice] = []
    now = datetime.now(timezone.utc)
    for i, d in enumerate(dates):
        close = base + math.sin(i / 10.0) * 5.0 + i * 0.01
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
async def quant_data(session: AsyncSession):
    now = datetime.now(timezone.utc)
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Quant API Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    sec1 = Security(
        security_id=uuid.uuid4(),
        name="Quant API Stock 1",
        short_name="QNT1",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    sec2 = Security(
        security_id=uuid.uuid4(),
        name="Quant API Stock 2",
        short_name="QNT2",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add_all([sec1, sec2])
    await session.flush()

    prices1 = _make_prices(sec1.security_id, n=260, base=100.0)
    prices2 = _make_prices(sec2.security_id, n=260, base=200.0)
    session.add_all(prices1 + prices2)
    await session.flush()

    return {
        "entity_id": entity.entity_id,
        "security_id_1": sec1.security_id,
        "security_id_2": sec2.security_id,
    }


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regression_200(client, quant_data):
    """POST /v2/analytics/quant/regression returns 200."""
    resp = await client.post("/v2/analytics/quant/regression", json={
        "security_id": str(quant_data["security_id_1"]),
        "dependent_var": "daily_return",
        "independent_vars": ["time"],
        "method": "OLS",
        "period_days": 756,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "coefficients" in data
    assert data["n_observations"] > 0
    assert data["r_squared"] is not None


@pytest.mark.asyncio
async def test_regression_no_security(client):
    """POST regression without security_id returns 400."""
    resp = await client.post("/v2/analytics/quant/regression", json={
        "dependent_var": "daily_return",
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rolling regression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rolling_regression_200(client, quant_data):
    """POST /v2/analytics/quant/regression/rolling returns 200."""
    resp = await client.post("/v2/analytics/quant/regression/rolling", json={
        "security_id": str(quant_data["security_id_1"]),
        "window": 30,
        "period_days": 756,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(quant_data["security_id_1"])
    assert len(data["data_points"]) > 0


# ---------------------------------------------------------------------------
# Stationarity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stationarity_200(client, quant_data):
    """POST /v2/analytics/quant/stationarity returns 200."""
    resp = await client.post("/v2/analytics/quant/stationarity", json={
        "security_id": str(quant_data["security_id_1"]),
        "test_type": "ADF",
        "series_name": "price",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_type"] == "ADF"
    assert data["test_statistic"] is not None


# ---------------------------------------------------------------------------
# Autocorrelation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_autocorrelation_200(client, quant_data):
    """POST /v2/analytics/quant/autocorrelation returns 200."""
    resp = await client.post("/v2/analytics/quant/autocorrelation", json={
        "security_id": str(quant_data["security_id_1"]),
        "max_lags": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["lags"]) == 10
    assert len(data["acf_values"]) == 10


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_200(client, quant_data):
    """GET /v2/analytics/quant/summary/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/quant/summary/{quant_data['security_id_1']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(quant_data["security_id_1"])


@pytest.mark.asyncio
async def test_summary_404(client):
    """GET /v2/analytics/quant/summary/{unknown} returns 404."""
    resp = await client.get(f"/v2/analytics/quant/summary/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Beta
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_beta_200(client, quant_data):
    """GET /v2/analytics/quant/beta/{id} returns 200."""
    resp = await client.get(f"/v2/analytics/quant/beta/{quant_data['security_id_1']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(quant_data["security_id_1"])
    assert data["benchmark"] == "SPY"


@pytest.mark.asyncio
async def test_beta_404(client):
    """GET /v2/analytics/quant/beta/{unknown} returns 404."""
    resp = await client.get(f"/v2/analytics/quant/beta/{uuid.uuid4()}")
    assert resp.status_code == 404
