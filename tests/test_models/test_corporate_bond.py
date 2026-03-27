"""Tests for Corporate Bond models (D11 FI Supplement P4)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.corporate_bond import (
    BondCallSchedule,
    BondEODPrice,
    BondTrade,
    CorporateBond,
)
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="CORPORATION",
        legal_name="Test Corp Inc.",
        short_name="TEST",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_bond(
    session,
    entity_id: uuid.UUID,
    cusip: str = "037833AK6",
    bond_id: uuid.UUID | None = None,
    **kwargs,
) -> CorporateBond:
    bid = bond_id or uuid.uuid4()
    defaults = {
        "bond_id": bid,
        "cusip": cusip,
        "issuer_entity_id": entity_id,
        "name": "Test Corp 5.00% 2035",
        "coupon_rate": 5.0,
        "coupon_type": "FIXED",
        "coupon_frequency": 2,
        "maturity_date": date(2035, 6, 15),
        "seniority": "SENIOR_UNSECURED",
        "currency": "USD",
        "status": "OUTSTANDING",
    }
    defaults.update(kwargs)
    bond = CorporateBond(**defaults)
    session.add(bond)
    await session.flush()
    return bond


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_corporate_bond(session):
    """Create a corporate bond with all required fields and verify CRUD."""
    entity = await _seed_entity(session)
    bid = uuid.uuid4()
    bond = CorporateBond(
        bond_id=bid,
        cusip="037833AK6",
        isin="US037833AK68",
        figi="BBG000B9Y5X2",
        issuer_entity_id=entity.entity_id,
        issuer_name="Test Corp Inc.",
        name="Test Corp 5.00% 2035",
        coupon_rate=5.0,
        coupon_type="FIXED",
        coupon_frequency=2,
        day_count_convention="30/360",
        issue_date=date(2025, 6, 15),
        maturity_date=date(2035, 6, 15),
        original_issue_amount=1_000_000_000.00,
        outstanding_amount=1_000_000_000.00,
        currency="USD",
        seniority="SENIOR_UNSECURED",
        is_callable=True,
        callable_from_date=date(2030, 6, 15),
        initial_rating_sp="BBB+",
        initial_rating_moodys="Baa1",
        is_investment_grade=True,
        status="OUTSTANDING",
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bid)
    )
    fetched = result.scalars().unique().one()
    assert fetched.cusip == "037833AK6"
    assert fetched.isin == "US037833AK68"
    assert fetched.name == "Test Corp 5.00% 2035"
    assert float(fetched.coupon_rate) == 5.0
    assert fetched.coupon_frequency == 2
    assert fetched.maturity_date == date(2035, 6, 15)
    assert fetched.is_callable is True
    assert fetched.is_investment_grade is True
    assert fetched.status == "OUTSTANDING"


@pytest.mark.asyncio
async def test_cusip_uniqueness(session):
    """Duplicate CUSIP should raise IntegrityError."""
    entity = await _seed_entity(session)
    cusip = "111111AA1"
    await _seed_bond(session, entity.entity_id, cusip=cusip)

    session.add(CorporateBond(
        cusip=cusip,
        issuer_entity_id=entity.entity_id,
        name="Duplicate Bond",
        maturity_date=date(2036, 1, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_call_schedule_relationship(session):
    """Bond with call schedule entries loaded via relationship."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="222222BB2", is_callable=True)

    cs1 = BondCallSchedule(
        bond_id=bond.bond_id,
        call_date=date(2030, 6, 15),
        call_price=101.0,
        call_type="MAKE_WHOLE",
    )
    cs2 = BondCallSchedule(
        bond_id=bond.bond_id,
        call_date=date(2032, 6, 15),
        call_price=100.5,
        call_type="PAR",
    )
    session.add_all([cs1, cs2])
    await session.flush()

    # Re-fetch bond to get relationship
    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bond.bond_id)
    )
    fetched = result.scalars().unique().one()
    assert len(fetched.call_schedule) == 2
    call_dates = sorted([cs.call_date for cs in fetched.call_schedule])
    assert call_dates == [date(2030, 6, 15), date(2032, 6, 15)]


@pytest.mark.asyncio
async def test_bond_trade_creation(session):
    """Create a TRACE trade record."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="333333CC3")

    tid = uuid.uuid4()
    trade = BondTrade(
        trade_id=tid,
        bond_id=bond.bond_id,
        trade_date=date(2025, 10, 1),
        price=98.5,
        yield_value=0.0525,
        quantity=1_000_000.00,
        trade_type="CUSTOMER_BUY",
        source="TRACE",
    )
    session.add(trade)
    await session.flush()

    result = await session.execute(
        select(BondTrade).where(BondTrade.trade_id == tid)
    )
    fetched = result.scalar_one()
    assert float(fetched.price) == pytest.approx(98.5, abs=0.01)
    assert float(fetched.quantity) == pytest.approx(1_000_000.0, abs=0.01)
    assert fetched.source == "TRACE"


@pytest.mark.asyncio
async def test_bond_eod_price_creation(session):
    """Create an EOD price record."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="444444DD4")

    pid = uuid.uuid4()
    eod = BondEODPrice(
        id=pid,
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=98.5,
        vwap=98.45,
        high_price=99.0,
        low_price=98.0,
        trade_count=12,
        total_volume=5_000_000.00,
        yield_to_maturity=0.0520,
        yield_to_worst=0.0510,
        g_spread_bps=150,
        liquidity_score=85,
        has_sufficient_trades=True,
        price_source="TRACE",
    )
    session.add(eod)
    await session.flush()

    result = await session.execute(
        select(BondEODPrice).where(BondEODPrice.id == pid)
    )
    fetched = result.scalar_one()
    assert float(fetched.last_trade_price) == pytest.approx(98.5, abs=0.01)
    assert fetched.trade_count == 12
    assert fetched.g_spread_bps == 150
    assert fetched.has_sufficient_trades is True


@pytest.mark.asyncio
async def test_bond_eod_unique_constraint(session):
    """Duplicate (bond_id, price_date) should raise IntegrityError."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="555555EE5")

    session.add(BondEODPrice(
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=98.5,
    ))
    await session.flush()

    session.add(BondEODPrice(
        bond_id=bond.bond_id,
        price_date=date(2025, 10, 1),
        last_trade_price=99.0,
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_issuer_fk(session):
    """Verify entity FK works — bond references valid entity."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="666666FF6")

    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bond.bond_id)
    )
    fetched = result.scalars().unique().one()
    assert fetched.issuer_entity_id == entity.entity_id


@pytest.mark.asyncio
async def test_bond_status_lifecycle(session):
    """Transition bond status from OUTSTANDING to CALLED."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(session, entity.entity_id, cusip="777777GG7")

    assert bond.status == "OUTSTANDING"

    bond.status = "CALLED"
    bond.status_date = date(2030, 6, 15)
    bond.status_reason = "Called at par"
    await session.flush()

    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bond.bond_id)
    )
    fetched = result.scalars().unique().one()
    assert fetched.status == "CALLED"
    assert fetched.status_date == date(2030, 6, 15)
    assert fetched.status_reason == "Called at par"


@pytest.mark.asyncio
async def test_optional_fields_null(session):
    """All optional fields can be null."""
    entity = await _seed_entity(session)
    bid = uuid.uuid4()
    bond = CorporateBond(
        bond_id=bid,
        cusip="888888HH8",
        issuer_entity_id=entity.entity_id,
        name="Minimal Bond",
        maturity_date=date(2040, 1, 1),
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bid)
    )
    fetched = result.scalars().unique().one()
    assert fetched.isin is None
    assert fetched.figi is None
    assert fetched.coupon_rate is None
    assert fetched.coupon_type is None
    assert fetched.coupon_frequency is None
    assert fetched.issue_date is None
    assert fetched.seniority is None
    assert fetched.initial_rating_sp is None
    assert fetched.conversion_price is None
    assert fetched.source_filing_accession is None


@pytest.mark.asyncio
async def test_covenant_flags(session):
    """All boolean covenant flags stored correctly."""
    entity = await _seed_entity(session)
    bond = await _seed_bond(
        session,
        entity.entity_id,
        cusip="999999II9",
        has_change_of_control_put=True,
        has_negative_pledge=True,
        has_leverage_covenant=True,
        has_interest_coverage_covenant=True,
    )

    result = await session.execute(
        select(CorporateBond).where(CorporateBond.bond_id == bond.bond_id)
    )
    fetched = result.scalars().unique().one()
    assert fetched.has_change_of_control_put is True
    assert fetched.has_negative_pledge is True
    assert fetched.has_leverage_covenant is True
    assert fetched.has_interest_coverage_covenant is True
