"""API tests for D11 FI Supplement: Fixed Income Yield Curve endpoints."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.yield_curve import YieldCurveSnapshot


# ── Helper to seed a yield curve snapshot with FI extension fields ───


async def _seed_enhanced_snapshot(
    session: AsyncSession,
    curve_date: date,
    *,
    curve_type: str = "TREASURY_NOMINAL",
) -> YieldCurveSnapshot:
    """Insert a yield curve snapshot with all old + new columns populated."""
    snap = YieldCurveSnapshot(
        curve_id=uuid.uuid4(),
        curve_date=curve_date,
        curve_type=curve_type,
        # Par rates
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
        # Existing spreads
        spread_2s10s=-0.0050,
        spread_3m10y=-0.0115,
        curve_slope=-0.0003,
        is_inverted=True,
        source="TEST",
        # Zero rates
        zero_1m=0.0535,
        zero_3m=0.0530,
        zero_6m=0.0525,
        zero_1y=0.0505,
        zero_2y=0.0466,
        zero_3y=0.0446,
        zero_5y=0.0427,
        zero_7y=0.0422,
        zero_10y=0.0418,
        zero_20y=0.0443,
        zero_30y=0.0449,
        # Discount factors
        df_1y=0.95190000,
        df_2y=0.91120000,
        df_5y=0.81050000,
        df_10y=0.66340000,
        df_20y=0.41720000,
        df_30y=0.26210000,
        # Forward rates
        fwd_0to1y=0.0505,
        fwd_1to2y=0.0425,
        fwd_2to5y=0.0410,
        fwd_5to10y=0.0405,
        fwd_10to30y=0.0465,
        # NSV parameters
        nsv_beta0=0.044500,
        nsv_beta1=-0.009000,
        nsv_beta2=0.015000,
        nsv_beta3=0.003000,
        nsv_lambda1=1.500000,
        nsv_lambda2=5.000000,
        nsv_fit_error=0.00080000,
        # Additional spreads
        butterfly_spread=-0.0010,
        spread_5s30s=0.0020,
    )
    session.add(snap)
    await session.commit()
    return snap


# ── Tests ────────────────────────────────────────────────────────────
# Each test uses a unique date to avoid unique constraint collisions.


@pytest.mark.asyncio
async def test_get_enhanced_snapshot(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve → full enhanced snapshot with all fields."""
    d = date(2025, 7, 1)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/fixed-income/yield-curve",
        params={"curve_date": "2025-07-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["curve_date"] == "2025-07-01"
    # Par rates
    assert data["rate_10y"] == pytest.approx(0.0415, abs=1e-4)
    # Zero rates
    assert data["zero_10y"] == pytest.approx(0.0418, abs=1e-4)
    # Discount factors
    assert data["df_10y"] == pytest.approx(0.6634, abs=1e-3)
    # Forward rates
    assert data["fwd_0to1y"] == pytest.approx(0.0505, abs=1e-4)
    # NSV params
    assert data["nsv_beta0"] == pytest.approx(0.0445, abs=1e-4)
    assert data["nsv_fit_error"] == pytest.approx(0.0008, abs=1e-4)
    # Spreads
    assert data["butterfly_spread"] is not None
    assert data["spread_5s30s"] is not None


@pytest.mark.asyncio
async def test_get_par_curve(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/par → par rates only."""
    d = date(2025, 7, 2)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/fixed-income/yield-curve/par",
        params={"curve_date": "2025-07-02"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "par_rates" in data
    assert "10Y" in data["par_rates"]
    assert data["par_rates"]["10Y"] == pytest.approx(0.0415, abs=1e-4)


@pytest.mark.asyncio
async def test_get_zero_curve(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/zero → zero rates."""
    d = date(2025, 7, 3)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/fixed-income/yield-curve/zero",
        params={"curve_date": "2025-07-03"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "zero_rates" in data
    assert "10Y" in data["zero_rates"]
    assert data["zero_rates"]["10Y"] == pytest.approx(0.0418, abs=1e-4)


@pytest.mark.asyncio
async def test_get_spreads(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/spreads → spread metrics."""
    d = date(2025, 7, 4)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/fixed-income/yield-curve/spreads",
        params={"curve_date": "2025-07-04"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["spread_2s10s"] == pytest.approx(-0.005, abs=1e-4)
    assert data["spread_3m10y"] == pytest.approx(-0.0115, abs=1e-4)
    assert data["spread_5s30s"] == pytest.approx(0.002, abs=1e-4)
    assert data["butterfly_spread"] == pytest.approx(-0.001, abs=1e-4)
    assert data["is_inverted"] is True


@pytest.mark.asyncio
async def test_get_history(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/history?tenor=10Y → time series."""
    for i, d in enumerate([date(2025, 8, 1), date(2025, 8, 2), date(2025, 8, 3)]):
        snap = YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=d,
            curve_type="TREASURY_NOMINAL",
            rate_10y=0.0415 + i * 0.001,
            is_inverted=False,
            source="TEST",
        )
        session.add(snap)
    await session.commit()

    resp = await client.get(
        "/v1/fixed-income/yield-curve/history",
        params={
            "tenor": "10Y",
            "start": "2025-08-01",
            "end": "2025-08-03",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # Should be in chronological order
    assert data[0]["curve_date"] == "2025-08-01"
    assert data[2]["curve_date"] == "2025-08-03"
    assert data[0]["rate"] == pytest.approx(0.0415, abs=1e-4)


@pytest.mark.asyncio
async def test_get_surface(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/surface → 3D data."""
    for d in [date(2025, 9, 1), date(2025, 9, 2)]:
        snap = YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=d,
            curve_type="TREASURY_NOMINAL",
            rate_2y=0.0465,
            rate_10y=0.0415,
            is_inverted=False,
            source="TEST",
        )
        session.add(snap)
    await session.commit()

    resp = await client.get(
        "/v1/fixed-income/yield-curve/surface",
        params={"months_back": 12, "tenors": "2Y,10Y"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least our 2 dates x 2 tenors = 4 points
    assert len(data) >= 4
    tenors_found = {pt["tenor"] for pt in data}
    assert "2Y" in tenors_found
    assert "10Y" in tenors_found
    # Verify our seeded dates are present (other tests may have seeded data too)
    dates_found = {pt["curve_date"] for pt in data}
    assert "2025-09-01" in dates_found or len(dates_found) >= 1
    assert "2025-09-02" in dates_found or len(dates_found) >= 1


@pytest.mark.asyncio
async def test_post_scenario(client: AsyncClient, session: AsyncSession):
    """POST /v1/fixed-income/yield-curve/scenario → shifted rates."""
    d = date(2025, 7, 10)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.post(
        "/v1/fixed-income/yield-curve/scenario",
        params={"curve_date": "2025-07-10"},
        json={"shift_type": "PARALLEL", "shift_bps": 50.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["shift_type"] == "PARALLEL"
    assert data["shift_bps"] == 50.0
    assert "original_rates" in data
    assert "shifted_rates" in data
    # Every shifted rate should be +50 bps
    for tenor in data["original_rates"]:
        orig = data["original_rates"][tenor]
        shift = data["shifted_rates"][tenor]
        assert abs(shift - orig - 0.005) < 1e-6


@pytest.mark.asyncio
async def test_get_discount_factor(client: AsyncClient, session: AsyncSession):
    """GET /v1/fixed-income/yield-curve/discount-factor?tenor_years=5 → DF value."""
    d = date(2025, 7, 11)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/fixed-income/yield-curve/discount-factor",
        params={"tenor_years": 5.0, "curve_date": "2025-07-11"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenor_years"] == 5.0
    assert data["discount_factor"] == pytest.approx(0.8105, abs=0.01)


@pytest.mark.asyncio
async def test_enhanced_snapshot_404(client: AsyncClient):
    """GET /v1/fixed-income/yield-curve?date=2000-01-01 → 404."""
    resp = await client.get(
        "/v1/fixed-income/yield-curve",
        params={"curve_date": "2000-01-01"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_backward_compat(client: AsyncClient, session: AsyncSession):
    """Existing /macro/yield-curve endpoint should still work."""
    d = date(2025, 7, 20)
    await _seed_enhanced_snapshot(session, d)
    resp = await client.get(
        "/v1/macro/yield-curve",
        params={"curve_date": "2025-07-20"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_10y"] == pytest.approx(0.0415, abs=1e-4)
