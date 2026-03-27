"""Tests for Pillar 4 Phase 1: NAVSnapshot and CorporateActionQueue models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.portfolio import Portfolio
from src.models.nav_snapshot import NAVSnapshot, CorporateActionQueue


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(session) -> Portfolio:
    p = Portfolio(
        id=uuid.uuid4(),
        user_id="nav-test-user",
        portfolio_name=f"NAV Test {uuid.uuid4().hex[:8]}",
        inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
    )
    session.add(p)
    await session.flush()
    return p


# ── NAVSnapshot Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_nav_snapshot(session):
    """Create a NAV snapshot with all fields."""
    portfolio = await _seed_portfolio(session)
    sid = uuid.uuid4()
    snap = NAVSnapshot(
        id=sid,
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 6, 15),
        nav=Decimal("105000.00"),
        market_value=Decimal("80000.00"),
        cash_balance=Decimal("25000.00"),
        unrealized_pnl=Decimal("5000.00"),
        daily_return=Decimal("0.00150000"),
        cumulative_return=Decimal("0.05000000"),
        benchmark_daily_return=Decimal("0.00100000"),
        benchmark_cumulative_return=Decimal("0.04000000"),
        positions_snapshot={"AAPL": {"shares": 100, "value": 15000}},
    )
    session.add(snap)
    await session.flush()

    result = await session.execute(
        select(NAVSnapshot).where(NAVSnapshot.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == portfolio.id
    assert fetched.snapshot_date == date(2025, 6, 15)
    assert fetched.nav == Decimal("105000.00")
    assert fetched.market_value == Decimal("80000.00")
    assert fetched.cash_balance == Decimal("25000.00")
    assert fetched.unrealized_pnl == Decimal("5000.00")
    assert fetched.daily_return == Decimal("0.00150000")
    assert fetched.cumulative_return == Decimal("0.05000000")
    assert fetched.benchmark_daily_return == Decimal("0.00100000")
    assert fetched.benchmark_cumulative_return == Decimal("0.04000000")


@pytest.mark.asyncio
async def test_nav_snapshot_unique_constraint(session):
    """Duplicate portfolio_id + snapshot_date raises IntegrityError."""
    portfolio = await _seed_portfolio(session)
    session.add(NAVSnapshot(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 7, 1),
        nav=Decimal("100000.00"),
    ))
    await session.flush()

    session.add(NAVSnapshot(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 7, 1),
        nav=Decimal("101000.00"),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_nav_snapshot_positions_jsonb(session):
    """Round-trip JSONB positions_snapshot."""
    portfolio = await _seed_portfolio(session)
    positions = {
        "AAPL": {"shares": 100, "value": 15000},
        "MSFT": {"shares": 50, "value": 12500},
    }
    sid = uuid.uuid4()
    session.add(NAVSnapshot(
        id=sid,
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 7, 5),
        nav=Decimal("127500.00"),
        positions_snapshot=positions,
    ))
    await session.flush()

    result = await session.execute(
        select(NAVSnapshot).where(NAVSnapshot.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.positions_snapshot == positions
    assert fetched.positions_snapshot["AAPL"]["shares"] == 100


@pytest.mark.asyncio
async def test_nav_snapshot_fk_to_portfolio(session):
    """Verify FK relationship to portfolio."""
    portfolio = await _seed_portfolio(session)
    sid = uuid.uuid4()
    session.add(NAVSnapshot(
        id=sid,
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 8, 1),
        nav=Decimal("100000.00"),
    ))
    await session.flush()

    result = await session.execute(
        select(NAVSnapshot).where(NAVSnapshot.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == portfolio.id


@pytest.mark.asyncio
async def test_nav_snapshot_return_precision(session):
    """Verify Numeric(12,8) precision for daily_return."""
    portfolio = await _seed_portfolio(session)
    sid = uuid.uuid4()
    session.add(NAVSnapshot(
        id=sid,
        portfolio_id=portfolio.id,
        snapshot_date=date(2025, 8, 5),
        nav=Decimal("100500.00"),
        daily_return=Decimal("0.00500000"),
    ))
    await session.flush()

    result = await session.execute(
        select(NAVSnapshot).where(NAVSnapshot.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.daily_return == Decimal("0.00500000")


# ── CorporateActionQueue Tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_create_corporate_action(session):
    """Create a corporate action queue entry with all fields."""
    portfolio = await _seed_portfolio(session)
    caid = uuid.uuid4()
    ca = CorporateActionQueue(
        id=caid,
        portfolio_id=portfolio.id,
        position_id=uuid.uuid4(),
        action_type="DIVIDEND",
        ticker="AAPL",
        ex_date=date(2025, 8, 10),
        payment_date=date(2025, 8, 15),
        details={"amount_per_share": 0.96, "currency": "USD"},
        status="PENDING",
    )
    session.add(ca)
    await session.flush()

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == caid)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == portfolio.id
    assert fetched.action_type == "DIVIDEND"
    assert fetched.ticker == "AAPL"
    assert fetched.ex_date == date(2025, 8, 10)
    assert fetched.payment_date == date(2025, 8, 15)
    assert fetched.status == "PENDING"
    assert fetched.details["amount_per_share"] == 0.96


@pytest.mark.asyncio
async def test_corporate_action_default_status(session):
    """Verify default status is PENDING."""
    portfolio = await _seed_portfolio(session)
    caid = uuid.uuid4()
    session.add(CorporateActionQueue(
        id=caid,
        portfolio_id=portfolio.id,
        action_type="SPLIT",
    ))
    await session.flush()

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == caid)
    )
    fetched = result.scalar_one()
    assert fetched.status == "PENDING"


@pytest.mark.asyncio
async def test_corporate_action_applied_transition(session):
    """Transition from PENDING to APPLIED."""
    portfolio = await _seed_portfolio(session)
    caid = uuid.uuid4()
    ca = CorporateActionQueue(
        id=caid,
        portfolio_id=portfolio.id,
        action_type="DIVIDEND",
        status="PENDING",
    )
    session.add(ca)
    await session.flush()

    ca.status = "APPLIED"
    ca.applied_at = datetime.now(timezone.utc)
    await session.flush()

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == caid)
    )
    fetched = result.scalar_one()
    assert fetched.status == "APPLIED"
    assert fetched.applied_at is not None


@pytest.mark.asyncio
async def test_corporate_action_dismissed_transition(session):
    """Transition from PENDING to DISMISSED."""
    portfolio = await _seed_portfolio(session)
    caid = uuid.uuid4()
    ca = CorporateActionQueue(
        id=caid,
        portfolio_id=portfolio.id,
        action_type="MERGER",
        status="PENDING",
    )
    session.add(ca)
    await session.flush()

    ca.status = "DISMISSED"
    await session.flush()

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == caid)
    )
    fetched = result.scalar_one()
    assert fetched.status == "DISMISSED"


@pytest.mark.asyncio
async def test_corporate_action_details_jsonb(session):
    """Round-trip JSONB details."""
    portfolio = await _seed_portfolio(session)
    caid = uuid.uuid4()
    details = {"ratio": "2:1", "effective_date": "2025-09-01"}
    session.add(CorporateActionQueue(
        id=caid,
        portfolio_id=portfolio.id,
        action_type="SPLIT",
        details=details,
    ))
    await session.flush()

    result = await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.id == caid)
    )
    fetched = result.scalar_one()
    assert fetched.details == details
    assert fetched.details["ratio"] == "2:1"
