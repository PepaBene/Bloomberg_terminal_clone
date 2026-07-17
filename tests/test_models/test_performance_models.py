"""Tests for Pillar 4 Phase 2: PerformanceSnapshot model."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.performance import PerformanceSnapshot
from src.models.portfolio import Portfolio


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session,
    user_id: str = "test-user",
    portfolio_name: str = "Perf Test Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "portfolio_name": portfolio_name,
        "portfolio_type": "REAL",
        "inception_date": date(2025, 1, 1),
        "initial_cash": Decimal("100000.00"),
        "current_cash": Decimal("100000.00"),
    }
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_performance_snapshot(
    session,
    portfolio_id: uuid.UUID,
    period_type: str = "MONTHLY",
    period_end: date = date(2025, 6, 30),
    **kwargs,
) -> PerformanceSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "period_type": period_type,
        "period_start": date(2025, 6, 1),
        "period_end": period_end,
        "twr_return": Decimal("0.02150000"),
        "mwr_return": Decimal("0.02100000"),
        "benchmark_return": Decimal("0.01800000"),
        "active_return": Decimal("0.00350000"),
        "sharpe_ratio": Decimal("1.250000"),
        "sortino_ratio": Decimal("1.480000"),
        "information_ratio": Decimal("0.850000"),
        "tracking_error": Decimal("0.041200"),
        "max_drawdown": Decimal("-0.085000"),
        "calmar_ratio": Decimal("0.950000"),
        "beta": Decimal("0.920000"),
        "alpha": Decimal("0.003500"),
        "volatility": Decimal("0.152000"),
        "up_capture": Decimal("1.050000"),
        "down_capture": Decimal("0.880000"),
        "batting_average": Decimal("0.550000"),
        "best_day": Decimal("0.03200000"),
        "worst_day": Decimal("-0.02800000"),
        "positive_days": 14,
        "negative_days": 8,
    }
    defaults.update(kwargs)
    snap = PerformanceSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


# ── CRUD ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_performance_snapshot(session):
    """Create a PerformanceSnapshot with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Perf Create")
    snap = await _seed_performance_snapshot(session, p.id)
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == p.id
    assert fetched.period_type == "MONTHLY"
    assert fetched.twr_return == Decimal("0.02150000")
    assert fetched.sharpe_ratio == Decimal("1.250000")


@pytest.mark.asyncio
async def test_performance_snapshot_period_types(session):
    """Different period types can be stored."""
    p = await _seed_portfolio(session, portfolio_name="Perf Period Types")
    for pt in ["DAILY", "MONTHLY", "QUARTERLY", "ANNUAL"]:
        period_end = (
            date(2025, 3, 1) if pt == "DAILY" else (
                date(2025, 3, 31) if pt == "MONTHLY" else (
                    date(2025, 6, 30) if pt == "QUARTERLY" else date(2025, 12, 31)
                )
            )
        )
        # period_start must not be after period_end (ck_perf_period_order);
        # the exact start date isn't what this test is checking, so pin it
        # to period_end for every period type.
        snap = await _seed_performance_snapshot(
            session, p.id,
            period_type=pt,
            period_start=period_end,
            period_end=period_end,
        )
        result = await session.execute(
            select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
        )
        fetched = result.scalar_one()
        assert fetched.period_type == pt


@pytest.mark.asyncio
async def test_performance_snapshot_decimal_precision_twr(session):
    """Verify Numeric(12,8) precision for twr_return."""
    p = await _seed_portfolio(session, portfolio_name="Perf TWR Precision")
    snap = await _seed_performance_snapshot(
        session, p.id,
        twr_return=Decimal("0.12345678"),
        period_end=date(2025, 7, 31),
    )
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.twr_return == Decimal("0.12345678")


@pytest.mark.asyncio
async def test_performance_snapshot_decimal_precision_ratio(session):
    """Verify Numeric(10,6) precision for ratio fields."""
    p = await _seed_portfolio(session, portfolio_name="Perf Ratio Precision")
    snap = await _seed_performance_snapshot(
        session, p.id,
        sharpe_ratio=Decimal("2.123456"),
        sortino_ratio=Decimal("3.654321"),
        period_end=date(2025, 8, 31),
    )
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.sharpe_ratio == Decimal("2.123456")
    assert fetched.sortino_ratio == Decimal("3.654321")


@pytest.mark.asyncio
async def test_performance_snapshot_nullable_fields(session):
    """Nullable fields default to None."""
    p = await _seed_portfolio(session, portfolio_name="Perf Nullable")
    snap = PerformanceSnapshot(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        period_type="DAILY",
        period_start=date(2025, 9, 1),
        period_end=date(2025, 9, 1),
    )
    session.add(snap)
    await session.flush()

    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.twr_return is None
    assert fetched.sharpe_ratio is None
    assert fetched.beta is None
    assert fetched.positive_days is None


@pytest.mark.asyncio
async def test_performance_snapshot_unique_constraint(session):
    """Duplicate (portfolio_id, period_type, period_end) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Perf Unique")
    await _seed_performance_snapshot(
        session, p.id, period_type="MONTHLY", period_end=date(2025, 10, 31)
    )
    session.add(PerformanceSnapshot(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        period_type="MONTHLY",
        period_start=date(2025, 10, 1),
        period_end=date(2025, 10, 31),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_performance_snapshot_update(session):
    """Update an existing performance snapshot."""
    p = await _seed_portfolio(session, portfolio_name="Perf Update")
    snap = await _seed_performance_snapshot(
        session, p.id, period_end=date(2025, 11, 30)
    )
    snap.twr_return = Decimal("0.05000000")
    snap.sharpe_ratio = Decimal("2.000000")
    await session.flush()

    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.twr_return == Decimal("0.05000000")
    assert fetched.sharpe_ratio == Decimal("2.000000")


@pytest.mark.asyncio
async def test_performance_snapshot_integer_fields(session):
    """Verify integer fields positive_days and negative_days."""
    p = await _seed_portfolio(session, portfolio_name="Perf Integers")
    snap = await _seed_performance_snapshot(
        session, p.id,
        positive_days=22,
        negative_days=0,
        period_end=date(2025, 12, 31),
    )
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.positive_days == 22
    assert fetched.negative_days == 0


@pytest.mark.asyncio
async def test_performance_snapshot_capture_ratios(session):
    """Verify up_capture and down_capture fields."""
    p = await _seed_portfolio(session, portfolio_name="Perf Capture")
    snap = await _seed_performance_snapshot(
        session, p.id,
        up_capture=Decimal("1.120000"),
        down_capture=Decimal("0.780000"),
        period_end=date(2026, 1, 31),
    )
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.up_capture == Decimal("1.120000")
    assert fetched.down_capture == Decimal("0.780000")


@pytest.mark.asyncio
async def test_performance_snapshot_best_worst_day(session):
    """Verify best_day and worst_day precision."""
    p = await _seed_portfolio(session, portfolio_name="Perf Best Worst")
    snap = await _seed_performance_snapshot(
        session, p.id,
        best_day=Decimal("0.05500000"),
        worst_day=Decimal("-0.04200000"),
        period_end=date(2026, 2, 28),
    )
    result = await session.execute(
        select(PerformanceSnapshot).where(PerformanceSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.best_day == Decimal("0.05500000")
    assert fetched.worst_day == Decimal("-0.04200000")
