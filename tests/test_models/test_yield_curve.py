"""Tests for yield curve models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.yield_curve import YieldCurveSnapshot, ZeroCouponCurve


@pytest.mark.asyncio
async def test_create_yield_curve_snapshot(session):
    """Test creating a yield curve snapshot."""
    curve_id = uuid.uuid4()
    snapshot = YieldCurveSnapshot(
        curve_id=curve_id,
        curve_date=date(2026, 3, 19),
        curve_type="TREASURY_NOMINAL",
        rate_1m=0.0530,
        rate_3m=0.0525,
        rate_6m=0.0510,
        rate_1y=0.0480,
        rate_2y=0.0445,
        rate_5y=0.0420,
        rate_10y=0.0435,
        rate_30y=0.0460,
        spread_2s10s=-0.0010,
        spread_3m10y=-0.0090,
        is_inverted=True,
        source="TREASURY_GOV",
    )
    session.add(snapshot)
    await session.flush()

    result = await session.execute(
        select(YieldCurveSnapshot).where(YieldCurveSnapshot.curve_id == curve_id)
    )
    fetched = result.scalar_one()
    assert fetched.curve_type == "TREASURY_NOMINAL"
    assert float(fetched.rate_10y) == pytest.approx(0.0435, abs=0.0001)
    assert fetched.is_inverted is True


@pytest.mark.asyncio
async def test_create_zero_coupon_curve(session):
    """Test creating zero-coupon curve points."""
    for tenor, rate, df in [(1.0, 0.048, 0.9524), (2.0, 0.0445, 0.9152), (5.0, 0.042, 0.8110)]:
        session.add(ZeroCouponCurve(
            id=uuid.uuid4(),
            curve_date=date(2026, 3, 19),
            tenor_years=tenor,
            zero_rate=rate,
            discount_factor=df,
            forward_rate=rate,
        ))
    await session.flush()

    result = await session.execute(
        select(ZeroCouponCurve)
        .where(ZeroCouponCurve.curve_date == date(2026, 3, 19))
        .order_by(ZeroCouponCurve.tenor_years.asc())
    )
    points = result.scalars().all()
    assert len(points) == 3
    assert float(points[0].tenor_years) == 1.0
    assert float(points[2].tenor_years) == 5.0


@pytest.mark.asyncio
async def test_yield_curve_history(session):
    """Test querying yield curve history across dates."""
    for day in [17, 18, 19]:
        session.add(YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=date(2026, 3, day),
            curve_type="TREASURY_NOMINAL",
            rate_10y=0.0435 + (day - 17) * 0.001,
        ))
    await session.flush()

    result = await session.execute(
        select(YieldCurveSnapshot)
        .where(YieldCurveSnapshot.curve_type == "TREASURY_NOMINAL")
        .order_by(YieldCurveSnapshot.curve_date.asc())
    )
    snapshots = result.scalars().all()
    assert len(snapshots) == 3


@pytest.mark.asyncio
async def test_multiple_curve_types(session):
    """Test storing different curve types on the same date."""
    for ctype in ["TREASURY_NOMINAL", "TREASURY_REAL", "TIPS"]:
        session.add(YieldCurveSnapshot(
            curve_id=uuid.uuid4(),
            curve_date=date(2026, 3, 20),
            curve_type=ctype,
            rate_10y=0.04,
        ))
    await session.flush()

    result = await session.execute(
        select(YieldCurveSnapshot).where(YieldCurveSnapshot.curve_date == date(2026, 3, 20))
    )
    snapshots = result.scalars().all()
    assert len(snapshots) == 3
    types = {s.curve_type for s in snapshots}
    assert types == {"TREASURY_NOMINAL", "TREASURY_REAL", "TIPS"}
