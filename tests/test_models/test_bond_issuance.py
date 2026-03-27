"""Tests for Bond Issuance model (D11 FI Supplement P7)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.bond_issuance import BondIssuance
from src.models.entity import Entity


async def _seed_entity(session):
    """Helper to create a minimal issuer entity."""
    entity = Entity(
        entity_type="PUBLIC_COMPANY",
        legal_name="Test Corp",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.flush()
    return entity


@pytest.mark.asyncio
async def test_create_issuance(session):
    """Create a bond issuance with all key fields."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    issuance = BondIssuance(
        issuance_id=iid,
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 6, 15),
        settlement_date=date(2025, 6, 18),
        announcement_date=date(2025, 6, 12),
        coupon_rate=5.250000,
        maturity_date=date(2035, 6, 15),
        seniority="SENIOR_UNSECURED",
        issue_price=99.500000,
        issue_yield=5.310000,
        issued_size_mm=1000.00,
        lead_left_bookrunner="Goldman Sachs",
        currency="USD",
    )
    session.add(issuance)
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuance_id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.issuer_entity_id == entity.entity_id
    assert fetched.pricing_date == date(2025, 6, 15)
    assert float(fetched.coupon_rate) == pytest.approx(5.25, abs=1e-4)
    assert fetched.seniority == "SENIOR_UNSECURED"
    assert fetched.lead_left_bookrunner == "Goldman Sachs"
    assert fetched.currency == "USD"


@pytest.mark.asyncio
async def test_issuance_with_bookrunners(session):
    """JSONB all_bookrunners list stores correctly."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    bookrunners = ["Goldman Sachs", "JP Morgan", "Citi"]
    issuance = BondIssuance(
        issuance_id=iid,
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 7, 1),
        maturity_date=date(2030, 7, 1),
        lead_left_bookrunner="Goldman Sachs",
        all_bookrunners=bookrunners,
        issued_size_mm=500.00,
        currency="USD",
    )
    session.add(issuance)
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuance_id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.all_bookrunners == ["Goldman Sachs", "JP Morgan", "Citi"]


@pytest.mark.asyncio
async def test_issuance_nullable_fields(session):
    """Minimal creation — only required fields."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    issuance = BondIssuance(
        issuance_id=iid,
        issuer_entity_id=entity.entity_id,
    )
    session.add(issuance)
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuance_id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.pricing_date is None
    assert fetched.coupon_rate is None
    assert fetched.maturity_date is None
    assert fetched.seniority is None
    assert fetched.all_bookrunners is None
    assert fetched.bond_id is None
    assert fetched.tightening_bps is None


@pytest.mark.asyncio
async def test_benchmark_issuance(session):
    """Create issuance with is_benchmark=True, is_144a=True."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    issuance = BondIssuance(
        issuance_id=iid,
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 8, 1),
        maturity_date=date(2035, 8, 1),
        issued_size_mm=2000.00,
        is_benchmark=True,
        is_144a=True,
        is_registered=False,
        currency="USD",
    )
    session.add(issuance)
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuance_id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.is_benchmark is True
    assert fetched.is_144a is True
    assert fetched.is_registered is False


@pytest.mark.asyncio
async def test_tightening_fields(session):
    """Initial talk and final spread fields store correctly."""
    entity = await _seed_entity(session)
    iid = uuid.uuid4()
    issuance = BondIssuance(
        issuance_id=iid,
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 9, 1),
        initial_talk_low_bps=150,
        initial_talk_high_bps=175,
        final_spread_bps=140,
        tightening_bps=22,
        currency="USD",
    )
    session.add(issuance)
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuance_id == iid)
    )
    fetched = result.scalar_one()
    assert fetched.initial_talk_low_bps == 150
    assert fetched.initial_talk_high_bps == 175
    assert fetched.final_spread_bps == 140
    assert fetched.tightening_bps == 22


@pytest.mark.asyncio
async def test_filter_by_entity(session):
    """Query issuances by issuer_entity_id."""
    entity_a = await _seed_entity(session)
    entity_b = await _seed_entity(session)

    session.add(BondIssuance(
        issuer_entity_id=entity_a.entity_id,
        pricing_date=date(2025, 1, 15),
        currency="USD",
    ))
    session.add(BondIssuance(
        issuer_entity_id=entity_b.entity_id,
        pricing_date=date(2025, 2, 15),
        currency="EUR",
    ))
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuer_entity_id == entity_a.entity_id)
    )
    issuances = result.scalars().all()
    assert len(issuances) >= 1
    assert all(i.issuer_entity_id == entity_a.entity_id for i in issuances)


@pytest.mark.asyncio
async def test_filter_by_date(session):
    """Query issuances by pricing_date range."""
    entity = await _seed_entity(session)
    session.add(BondIssuance(
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 3, 1),
        currency="USD",
    ))
    session.add(BondIssuance(
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 6, 1),
        currency="USD",
    ))
    session.add(BondIssuance(
        issuer_entity_id=entity.entity_id,
        pricing_date=date(2025, 9, 1),
        currency="USD",
    ))
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(
            BondIssuance.pricing_date >= date(2025, 4, 1),
            BondIssuance.pricing_date <= date(2025, 7, 31),
        )
    )
    issuances = result.scalars().all()
    assert len(issuances) >= 1
    for i in issuances:
        assert date(2025, 4, 1) <= i.pricing_date <= date(2025, 7, 31)


@pytest.mark.asyncio
async def test_multiple_issuances(session):
    """Create several issuances and verify count."""
    entity = await _seed_entity(session)
    for month in range(1, 6):
        session.add(BondIssuance(
            issuer_entity_id=entity.entity_id,
            pricing_date=date(2025, month, 15),
            issued_size_mm=500.00 + month * 100,
            currency="USD",
        ))
    await session.flush()

    result = await session.execute(
        select(BondIssuance).where(BondIssuance.issuer_entity_id == entity.entity_id)
    )
    issuances = result.scalars().all()
    assert len(issuances) >= 5
