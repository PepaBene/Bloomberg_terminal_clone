"""Tests for Pillar 4 Phase 1: Position model."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.portfolio import Portfolio
from src.models.position import Position


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(session) -> Portfolio:
    p = Portfolio(
        id=uuid.uuid4(),
        user_id="pos-test-user",
        portfolio_name=f"Pos Test {uuid.uuid4().hex[:8]}",
        inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
    )
    session.add(p)
    await session.flush()
    return p


async def _seed_position(
    session, portfolio_id: uuid.UUID, ticker: str = "AAPL", **kwargs
) -> Position:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "ticker": ticker,
        "status": "OPEN",
        "shares": Decimal("100.000000"),
        "cost_basis_per_share": Decimal("150.500000"),
        "cost_basis_total": Decimal("15050.00"),
        "first_acquisition_date": date(2025, 3, 1),
    }
    defaults.update(kwargs)
    pos = Position(**defaults)
    session.add(pos)
    await session.flush()
    return pos


# ── Position CRUD ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_position(session):
    """Create a position with all fields."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session,
        portfolio.id,
        ticker="MSFT",
        market_value=Decimal("25000.00"),
        unrealized_pnl=Decimal("1500.00"),
        unrealized_pnl_pct=Decimal("6.3830"),
        weight=Decimal("25.0000"),
        closing_price=Decimal("250.0000"),
        day_change_pct=Decimal("1.2500"),
        notes="Tech holding",
    )
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == portfolio.id
    assert fetched.ticker == "MSFT"
    assert fetched.status == "OPEN"
    assert fetched.shares == Decimal("100.000000")
    assert fetched.cost_basis_per_share == Decimal("150.500000")
    assert fetched.cost_basis_total == Decimal("15050.00")
    assert fetched.market_value == Decimal("25000.00")
    assert fetched.unrealized_pnl == Decimal("1500.00")
    assert fetched.unrealized_pnl_pct == Decimal("6.3830")
    assert fetched.weight == Decimal("25.0000")
    assert fetched.closing_price == Decimal("250.0000")
    assert fetched.day_change_pct == Decimal("1.2500")
    assert fetched.notes == "Tech holding"


@pytest.mark.asyncio
async def test_position_fk_to_portfolio(session):
    """Verify FK relationship to portfolio."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(session, portfolio.id)
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == portfolio.id


@pytest.mark.asyncio
async def test_position_default_status(session):
    """Verify default status is OPEN."""
    portfolio = await _seed_portfolio(session)
    pid = uuid.uuid4()
    session.add(Position(
        id=pid,
        portfolio_id=portfolio.id,
        ticker="GOOG",
    ))
    await session.flush()

    result = await session.execute(
        select(Position).where(Position.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.status == "OPEN"


@pytest.mark.asyncio
async def test_position_closed_status(session):
    """Transition position from OPEN to CLOSED."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(session, portfolio.id, ticker="TSLA")
    pos.status = "CLOSED"
    await session.flush()

    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "CLOSED"


@pytest.mark.asyncio
async def test_position_unique_constraint(session):
    """Duplicate portfolio_id + ticker + status raises IntegrityError."""
    portfolio = await _seed_portfolio(session)
    await _seed_position(session, portfolio.id, ticker="DUP")
    session.add(Position(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        ticker="DUP",
        status="OPEN",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_position_same_ticker_different_status(session):
    """Same ticker with OPEN + CLOSED is allowed (different status)."""
    portfolio = await _seed_portfolio(session)
    await _seed_position(session, portfolio.id, ticker="AMZN", status="OPEN")
    pos2 = await _seed_position(session, portfolio.id, ticker="AMZN", status="CLOSED")
    result = await session.execute(
        select(Position).where(Position.id == pos2.id)
    )
    fetched = result.scalar_one()
    assert fetched.ticker == "AMZN"
    assert fetched.status == "CLOSED"


@pytest.mark.asyncio
async def test_position_shares_decimal_precision(session):
    """Verify Numeric(20,6) precision for shares."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session, portfolio.id, ticker="BTC",
        shares=Decimal("0.123456"),
    )
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.shares == Decimal("0.123456")


@pytest.mark.asyncio
async def test_position_cost_basis_precision(session):
    """Verify Numeric(15,6) precision for cost_basis_per_share."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session, portfolio.id, ticker="ETH",
        cost_basis_per_share=Decimal("2345.678901"),
    )
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.cost_basis_per_share == Decimal("2345.678901")


@pytest.mark.asyncio
async def test_position_market_value_precision(session):
    """Verify Numeric(20,2) precision for market_value."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session, portfolio.id, ticker="NVDA",
        market_value=Decimal("99999999.99"),
    )
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.market_value == Decimal("99999999.99")


@pytest.mark.asyncio
async def test_position_security_id_nullable(session):
    """Verify security_id can be null."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(session, portfolio.id, ticker="XYZ")
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.security_id is None


@pytest.mark.asyncio
async def test_position_update_shares(session):
    """Update shares after a transaction."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session, portfolio.id, ticker="META",
        shares=Decimal("50.000000"),
    )
    pos.shares = Decimal("75.000000")
    await session.flush()

    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.shares == Decimal("75.000000")


@pytest.mark.asyncio
async def test_position_notes(session):
    """Verify notes text field."""
    portfolio = await _seed_portfolio(session)
    pos = await _seed_position(
        session, portfolio.id, ticker="NFLX",
        notes="Streaming play",
    )
    result = await session.execute(
        select(Position).where(Position.id == pos.id)
    )
    fetched = result.scalar_one()
    assert fetched.notes == "Streaming play"
