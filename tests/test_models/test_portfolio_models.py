"""Tests for Pillar 4 Phase 1: Portfolio model."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.portfolio import Portfolio


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session,
    user_id: str = "test-user",
    portfolio_name: str = "Test Portfolio",
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


# ── Portfolio CRUD ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_portfolio(session):
    """Create a portfolio with all fields."""
    p = await _seed_portfolio(
        session,
        benchmark_id="SPX",
        base_currency="USD",
        tags={"strategy": "growth"},
        notes="My test portfolio",
    )
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "test-user"
    assert fetched.portfolio_name == "Test Portfolio"
    assert fetched.portfolio_type == "REAL"
    assert fetched.benchmark_id == "SPX"
    assert fetched.inception_date == date(2025, 1, 1)
    assert fetched.initial_cash == Decimal("100000.00")
    assert fetched.current_cash == Decimal("100000.00")
    assert fetched.base_currency == "USD"
    assert fetched.tags == {"strategy": "growth"}
    assert fetched.notes == "My test portfolio"


@pytest.mark.asyncio
async def test_portfolio_default_status(session):
    """Verify default status is ACTIVE."""
    p = await _seed_portfolio(session, portfolio_name="Default Status")
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "ACTIVE"


@pytest.mark.asyncio
async def test_portfolio_default_type(session):
    """Verify default portfolio_type is REAL."""
    pid = uuid.uuid4()
    session.add(Portfolio(
        id=pid,
        user_id="test-user",
        portfolio_name="Type Default",
        inception_date=date(2025, 1, 1),
        initial_cash=Decimal("50000.00"),
        current_cash=Decimal("50000.00"),
    ))
    await session.flush()

    result = await session.execute(
        select(Portfolio).where(Portfolio.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_type == "REAL"


@pytest.mark.asyncio
async def test_portfolio_default_currency(session):
    """Verify default base_currency is USD."""
    p = await _seed_portfolio(session, portfolio_name="Currency Default")
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.base_currency == "USD"


@pytest.mark.asyncio
async def test_portfolio_update_cash(session):
    """Update current_cash after a transaction."""
    p = await _seed_portfolio(session, portfolio_name="Cash Update")
    p.current_cash = Decimal("75000.50")
    await session.flush()

    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.current_cash == Decimal("75000.50")


@pytest.mark.asyncio
async def test_portfolio_update_status(session):
    """Update status to ARCHIVED."""
    p = await _seed_portfolio(session, portfolio_name="Archive Test")
    p.status = "ARCHIVED"
    await session.flush()

    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "ARCHIVED"


@pytest.mark.asyncio
async def test_portfolio_unique_constraint(session):
    """Duplicate user_id + portfolio_name raises IntegrityError."""
    await _seed_portfolio(session, user_id="dup-user", portfolio_name="Dup Portfolio")
    session.add(Portfolio(
        id=uuid.uuid4(),
        user_id="dup-user",
        portfolio_name="Dup Portfolio",
        inception_date=date(2025, 6, 1),
        initial_cash=Decimal("10000.00"),
        current_cash=Decimal("10000.00"),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_portfolio_tags_jsonb_roundtrip(session):
    """Round-trip JSONB tags."""
    tags = {"sectors": ["TECH", "ENERGY"], "risk_level": "HIGH"}
    p = await _seed_portfolio(session, portfolio_name="Tags Test", tags=tags)
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.tags == tags
    assert fetched.tags["sectors"] == ["TECH", "ENERGY"]
    assert fetched.tags["risk_level"] == "HIGH"


@pytest.mark.asyncio
async def test_portfolio_tags_null(session):
    """Tags can be null."""
    p = await _seed_portfolio(session, portfolio_name="Null Tags")
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.tags is None


@pytest.mark.asyncio
async def test_portfolio_initial_cash_decimal_precision(session):
    """Verify Numeric(20,2) precision for initial_cash."""
    p = await _seed_portfolio(
        session,
        portfolio_name="Precision Cash",
        initial_cash=Decimal("1234567890.99"),
        current_cash=Decimal("1234567890.99"),
    )
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.initial_cash == Decimal("1234567890.99")


@pytest.mark.asyncio
async def test_portfolio_paper_type(session):
    """Create a PAPER portfolio."""
    p = await _seed_portfolio(
        session, portfolio_name="Paper Portfolio", portfolio_type="PAPER"
    )
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_type == "PAPER"


@pytest.mark.asyncio
async def test_portfolio_multiple_users(session):
    """Different users can have same portfolio name."""
    await _seed_portfolio(session, user_id="user-a", portfolio_name="SharedName")
    p2 = await _seed_portfolio(session, user_id="user-b", portfolio_name="SharedName")
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p2.id)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "user-b"
    assert fetched.portfolio_name == "SharedName"


@pytest.mark.asyncio
async def test_portfolio_notes_text(session):
    """Verify long text in notes."""
    long_note = "A" * 5000
    p = await _seed_portfolio(
        session, portfolio_name="Long Notes", notes=long_note
    )
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert len(fetched.notes) == 5000


@pytest.mark.asyncio
async def test_portfolio_benchmark_id(session):
    """Verify benchmark_id can be set and read."""
    p = await _seed_portfolio(
        session, portfolio_name="Benchmark Test", benchmark_id="SPY"
    )
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == p.id)
    )
    fetched = result.scalar_one()
    assert fetched.benchmark_id == "SPY"
