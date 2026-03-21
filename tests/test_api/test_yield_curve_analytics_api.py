"""API tests for yield curve analytics endpoints (Pillar 2 Supplement – Part 1)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.yield_curve import YieldCurveSnapshot
from src.models.yield_curve_analytics import CurveAnalytics, YieldCurveFitted


# ── Helper to seed a yield curve snapshot ────────────────────────────

async def _seed_snapshot(session: AsyncSession, curve_date: date) -> YieldCurveSnapshot:
    """Insert a realistic yield curve snapshot for testing."""
    snap = YieldCurveSnapshot(
        curve_id=uuid.uuid4(),
        curve_date=curve_date,
        curve_type="TREASURY_NOMINAL",
        rate_1m=0.0535,
        rate_3m=0.0530,
        rate_6m=0.0525,
        rate_1y=0.0505,
        rate_2y=0.0465,
        rate_3y=0.0445,
        rate_5y=0.0425,
        rate_7y=0.0420,
        rate_10y=0.0415,
        rate_20y=0.0440,
        rate_30y=0.0445,
        spread_2s10s=-0.0050,
        spread_3m10y=-0.0115,
        curve_slope=-0.0003,
        is_inverted=True,
        source="TEST",
    )
    session.add(snap)
    await session.commit()
    return snap


async def _seed_fitted(session: AsyncSession, curve_date: date) -> YieldCurveFitted:
    """Insert a cached Nelson-Siegel fit."""
    fitted = YieldCurveFitted(
        fit_id=uuid.uuid4(),
        curve_date=curve_date,
        curve_type="TREASURY_NOMINAL",
        method="NELSON_SIEGEL",
        beta0=0.044,
        beta1=-0.008,
        beta2=0.015,
        tau=1.8,
        fit_error=0.001,
        fitted_rates={
            "0.25": 0.053, "0.5": 0.052, "1.0": 0.050,
            "2.0": 0.047, "5.0": 0.043, "10.0": 0.042,
            "30.0": 0.044,
        },
    )
    session.add(fitted)
    await session.commit()
    return fitted


async def _seed_curve_analytics(session: AsyncSession, curve_date: date) -> CurveAnalytics:
    """Insert cached curve analytics."""
    analytics = CurveAnalytics(
        id=uuid.uuid4(),
        curve_date=curve_date,
        spread_2s10s=-0.0050,
        spread_3m10y=-0.0115,
        steepness=-0.0003,
        curvature=0.0015,
        breakeven_5y=0.0225,
        breakeven_10y=0.0225,
        is_inverted=True,
    )
    session.add(analytics)
    await session.commit()
    return analytics


# ── Tests ────────────────────────────────────────────────────────────
# Each test uses a unique date to avoid unique constraint collisions.


@pytest.mark.asyncio
async def test_get_fitted_curve_cached(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve should return cached NS fit when available."""
    d = date(2024, 1, 1)
    await _seed_fitted(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve",
        params={"curve_date": "2024-01-01", "method": "NELSON_SIEGEL"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "NELSON_SIEGEL"
    assert data["params"] is not None
    assert data["params"]["beta0"] == pytest.approx(0.044, abs=1e-4)
    assert len(data["points"]) > 0


@pytest.mark.asyncio
async def test_get_fitted_curve_computed(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve computes from snapshot when no cache."""
    d = date(2024, 1, 2)
    await _seed_snapshot(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve",
        params={"curve_date": "2024-01-02", "method": "NELSON_SIEGEL"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "NELSON_SIEGEL"
    assert data["params"] is not None
    assert data["params"]["fit_error"] < 0.01
    assert len(data["points"]) >= 11  # standard tenors + input tenors


@pytest.mark.asyncio
async def test_get_fitted_curve_404(client: AsyncClient):
    """GET /v1/analytics/yield-curve with no data returns 404."""
    resp = await client.get(
        "/v1/analytics/yield-curve",
        params={"curve_date": "2000-01-01"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_spreads_cached(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/spreads returns cached analytics."""
    d = date(2024, 2, 1)
    await _seed_curve_analytics(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/spreads",
        params={"curve_date": "2024-02-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["spread_2s10s"] == pytest.approx(-0.005, abs=1e-4)
    assert data["is_inverted"] is True


@pytest.mark.asyncio
async def test_get_spreads_computed(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/spreads computes from snapshot when no cache."""
    d = date(2024, 2, 2)
    await _seed_snapshot(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/spreads",
        params={"curve_date": "2024-02-02"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["spread_2s10s"] is not None
    assert data["steepness"] is not None
    assert data["curvature"] is not None


@pytest.mark.asyncio
async def test_get_interpolated_rate(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/rate returns interpolated rate."""
    d = date(2024, 3, 1)
    await _seed_snapshot(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/rate",
        params={"tenor": "10Y", "curve_date": "2024-03-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenor_years"] == 10.0
    assert data["rate"] == pytest.approx(0.0415, abs=0.001)
    assert data["interpolation_method"] == "LINEAR"


@pytest.mark.asyncio
async def test_get_interpolated_rate_custom_tenor(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/rate with a non-standard tenor."""
    d = date(2024, 3, 2)
    await _seed_snapshot(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/rate",
        params={"tenor": "4.0", "curve_date": "2024-03-02", "method": "LINEAR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenor_years"] == 4.0
    assert 0.040 < data["rate"] < 0.050


@pytest.mark.asyncio
async def test_post_scenario_parallel(client: AsyncClient, session: AsyncSession):
    """POST /v1/analytics/yield-curve/scenario applies a parallel shift."""
    d = date(2024, 4, 1)
    await _seed_snapshot(session, d)
    resp = await client.post(
        "/v1/analytics/yield-curve/scenario",
        params={"curve_date": "2024-04-01"},
        json={"shift_type": "PARALLEL", "shift_bps": 50.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["shift_type"] == "PARALLEL"
    assert data["shift_bps"] == 50.0
    assert len(data["points"]) > 0
    for pt in data["points"]:
        assert abs(pt["shift_bps"] - 50.0) < 0.01


@pytest.mark.asyncio
async def test_get_spread_history(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/spreads/history returns time series."""
    d = date(2024, 5, 1)
    await _seed_curve_analytics(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/spreads/history",
        params={"spread_type": "2s10s"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["spread_type"] == "2s10s"
    assert len(data["points"]) > 0


@pytest.mark.asyncio
async def test_get_nelson_siegel_params(client: AsyncClient, session: AsyncSession):
    """GET /v1/analytics/yield-curve/fitted returns NS params."""
    d = date(2024, 6, 1)
    await _seed_snapshot(session, d)
    resp = await client.get(
        "/v1/analytics/yield-curve/fitted",
        params={"curve_date": "2024-06-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "NELSON_SIEGEL"
    assert data["params"] is not None
    assert "beta0" in data["params"]
    assert "tau" in data["params"]
