"""Tests for Yield Curve API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.yield_curve import YieldCurveSnapshot, ZeroCouponCurve


@pytest.mark.asyncio
async def test_get_yield_curve_not_found(client):
    """Test 404 when no yield curve data exists."""
    response = await client.get("/v1/macro/yield-curve")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_yield_curve(client, session):
    """Test fetching the latest yield curve."""
    session.add(YieldCurveSnapshot(
        curve_id=uuid.uuid4(),
        curve_date=date(2026, 3, 19),
        curve_type="TREASURY_NOMINAL",
        rate_2y=0.0445,
        rate_10y=0.0435,
        spread_2s10s=-0.0010,
        is_inverted=True,
        source="TREASURY_GOV",
    ))
    await session.flush()

    response = await client.get("/v1/macro/yield-curve")
    assert response.status_code == 200
    data = response.json()
    assert data["curve_type"] == "TREASURY_NOMINAL"
    assert data["is_inverted"] is True


@pytest.mark.asyncio
async def test_get_yield_curve_by_date(client, session):
    """Test fetching yield curve for a specific date."""
    for day in [18, 19]:
        session.add(YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=date(2026, 3, day),
            curve_type="TREASURY_NOMINAL",
            rate_10y=0.0435 + (day - 18) * 0.001,
        ))
    await session.flush()

    response = await client.get(
        "/v1/macro/yield-curve",
        params={"curve_date": "2026-03-18"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["curve_date"] == "2026-03-18"


@pytest.mark.asyncio
async def test_yield_curve_history_empty(client):
    """Test yield curve history when empty."""
    response = await client.get("/v1/macro/yield-curve/history")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_yield_curve_history(client, session):
    """Test fetching yield curve history."""
    for day in [17, 18, 19]:
        session.add(YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=date(2026, 3, day),
            curve_type="TREASURY_NOMINAL",
            rate_10y=0.04,
        ))
    await session.flush()

    response = await client.get(
        "/v1/macro/yield-curve/history",
        params={"start": "2026-03-17", "end": "2026-03-19"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_forward_curve_not_found(client):
    """Test 404 when no forward curve data."""
    response = await client.get("/v1/macro/yield-curve/forwards")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_forward_curve(client, session):
    """Test fetching the bootstrapped forward curve."""
    for tenor, rate in [(1.0, 0.048), (2.0, 0.0445), (5.0, 0.042)]:
        session.add(ZeroCouponCurve(
            id=uuid.uuid4(),
            curve_date=date(2026, 3, 19),
            tenor_years=tenor,
            zero_rate=rate,
            discount_factor=0.95,
            forward_rate=rate,
        ))
    await session.flush()

    response = await client.get(
        "/v1/macro/yield-curve/forwards",
        params={"curve_date": "2026-03-19"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["curve_date"] == "2026-03-19"
    assert len(data["points"]) == 3


@pytest.mark.asyncio
async def test_forward_curve_latest(client, session):
    """Test that /forwards defaults to the latest date."""
    session.add(ZeroCouponCurve(
        id=uuid.uuid4(),
        curve_date=date(2026, 3, 20),
        tenor_years=1.0,
        zero_rate=0.048,
        discount_factor=0.95,
        forward_rate=0.048,
    ))
    await session.flush()

    response = await client.get("/v1/macro/yield-curve/forwards")
    assert response.status_code == 200
    data = response.json()
    assert data["curve_date"] == "2026-03-20"
