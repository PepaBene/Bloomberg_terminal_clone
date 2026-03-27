"""Tests for Pillar 3 Phase 1: Insider Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.insider_intelligence import InsiderSignal, InsiderTransactionP3


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Insider Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_insider_transaction(session):
    """Create an insider transaction with all fields including Decimal precision."""
    entity = await _seed_entity(session)
    tid = uuid.uuid4()
    txn = InsiderTransactionP3(
        id=tid,
        entity_id=entity.entity_id,
        reporting_person="John Q. Executive",
        reporting_person_cik="0001234567",
        relationship="CEO",
        transaction_type="PURCHASE",
        transaction_code="P",
        transaction_date=date(2025, 8, 15),
        shares=Decimal("10000.00"),
        price_per_share=Decimal("152.7500"),
        total_value=Decimal("1527500.00"),
        shares_owned_after=Decimal("250000.00"),
        is_open_market=True,
        is_10b5_1=False,
        is_direct_ownership=True,
        filing_date=date(2025, 8, 17),
        filing_url="https://sec.gov/form4/example",
    )
    session.add(txn)
    await session.flush()

    result = await session.execute(
        select(InsiderTransactionP3).where(InsiderTransactionP3.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.reporting_person == "John Q. Executive"
    assert fetched.reporting_person_cik == "0001234567"
    assert fetched.relationship == "CEO"
    assert fetched.transaction_type == "PURCHASE"
    assert fetched.transaction_code == "P"
    assert fetched.transaction_date == date(2025, 8, 15)
    assert fetched.shares == Decimal("10000.00")
    assert fetched.price_per_share == Decimal("152.7500")
    assert fetched.total_value == Decimal("1527500.00")
    assert fetched.shares_owned_after == Decimal("250000.00")
    assert fetched.is_open_market is True
    assert fetched.is_10b5_1 is False
    assert fetched.is_direct_ownership is True


@pytest.mark.asyncio
async def test_insider_transaction_open_market_flag(session):
    """Test is_open_market and is_10b5_1 boolean fields."""
    entity = await _seed_entity(session)

    # Open-market, non-10b5-1
    tid1 = uuid.uuid4()
    session.add(InsiderTransactionP3(
        id=tid1,
        entity_id=entity.entity_id,
        reporting_person="Open Market Buyer",
        relationship="CFO",
        transaction_type="PURCHASE",
        transaction_date=date(2025, 9, 1),
        is_open_market=True,
        is_10b5_1=False,
    ))
    # 10b5-1 plan sale
    tid2 = uuid.uuid4()
    session.add(InsiderTransactionP3(
        id=tid2,
        entity_id=entity.entity_id,
        reporting_person="Plan Seller",
        relationship="VP",
        transaction_type="SALE",
        transaction_date=date(2025, 9, 2),
        is_open_market=False,
        is_10b5_1=True,
    ))
    await session.flush()

    r1 = await session.execute(
        select(InsiderTransactionP3).where(InsiderTransactionP3.id == tid1)
    )
    f1 = r1.scalar_one()
    assert f1.is_open_market is True
    assert f1.is_10b5_1 is False

    r2 = await session.execute(
        select(InsiderTransactionP3).where(InsiderTransactionP3.id == tid2)
    )
    f2 = r2.scalar_one()
    assert f2.is_open_market is False
    assert f2.is_10b5_1 is True


@pytest.mark.asyncio
async def test_create_insider_signal(session):
    """Create an insider signal with signal_type, signal_strength, rolling aggregates."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    signal = InsiderSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date(2025, 10, 1),
        signal_type="CLUSTER_BUY",
        signal_strength=85,
        net_shares_30d=Decimal("50000.00"),
        net_value_30d=Decimal("7500000.00"),
        net_shares_90d=Decimal("120000.00"),
        net_value_90d=Decimal("18000000.00"),
        net_shares_365d=Decimal("200000.00"),
        net_value_365d=Decimal("30000000.00"),
        open_market_buy_count_90d=7,
        insider_count_buying_30d=4,
        insider_count_selling_30d=1,
        ownership_pct_change=Decimal("2.5000"),
        detail={"top_buyer": "CEO", "avg_purchase_size": 12500},
    )
    session.add(signal)
    await session.flush()

    result = await session.execute(
        select(InsiderSignal).where(InsiderSignal.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.signal_type == "CLUSTER_BUY"
    assert fetched.signal_strength == 85
    assert fetched.net_shares_30d == Decimal("50000.00")
    assert fetched.net_value_30d == Decimal("7500000.00")
    assert fetched.net_shares_90d == Decimal("120000.00")
    assert fetched.net_value_90d == Decimal("18000000.00")
    assert fetched.open_market_buy_count_90d == 7
    assert fetched.insider_count_buying_30d == 4
    assert fetched.insider_count_selling_30d == 1
    assert fetched.ownership_pct_change == Decimal("2.5000")


@pytest.mark.asyncio
async def test_insider_signal_unique_constraint(session):
    """entity_id + signal_date + signal_type should be unique."""
    entity = await _seed_entity(session)
    common = dict(
        entity_id=entity.entity_id,
        signal_date=date(2025, 10, 15),
        signal_type="CLUSTER_BUY",
        signal_strength=50,
    )
    session.add(InsiderSignal(**common))
    await session.flush()

    session.add(InsiderSignal(**{**common, "signal_strength": 75}))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_query_insider_transactions_by_entity(session):
    """Create multiple transactions, filter by entity + date range."""
    entity = await _seed_entity(session)
    for day in (1, 5, 15, 25):
        session.add(InsiderTransactionP3(
            entity_id=entity.entity_id,
            reporting_person=f"Insider {day}",
            relationship="OFFICER",
            transaction_type="PURCHASE",
            transaction_date=date(2025, 11, day),
            is_open_market=True,
            is_10b5_1=False,
        ))
    await session.flush()

    result = await session.execute(
        select(InsiderTransactionP3)
        .where(InsiderTransactionP3.entity_id == entity.entity_id)
        .where(InsiderTransactionP3.transaction_date >= date(2025, 11, 3))
        .where(InsiderTransactionP3.transaction_date <= date(2025, 11, 20))
    )
    txns = result.scalars().all()
    assert len(txns) == 2
    names = sorted(t.reporting_person for t in txns)
    assert names == ["Insider 15", "Insider 5"]


@pytest.mark.asyncio
async def test_insider_signal_detail_jsonb(session):
    """Round-trip JSONB detail field."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    detail = {
        "top_insiders": [
            {"name": "Alice CEO", "net_shares": 50000},
            {"name": "Bob CFO", "net_shares": 20000},
        ],
        "cluster_score": 92,
        "days_since_last": 3,
    }
    session.add(InsiderSignal(
        id=sid,
        entity_id=entity.entity_id,
        signal_date=date(2025, 12, 1),
        signal_type="CLUSTER_SELL",
        signal_strength=40,
        detail=detail,
    ))
    await session.flush()

    result = await session.execute(
        select(InsiderSignal).where(InsiderSignal.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.detail == detail
    assert fetched.detail["cluster_score"] == 92
    assert len(fetched.detail["top_insiders"]) == 2
    assert fetched.detail["top_insiders"][0]["name"] == "Alice CEO"
