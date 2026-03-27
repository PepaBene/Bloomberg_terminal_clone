"""Tests for Treasury Securities model (D11 FI Supplement P2)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.treasury import TreasurySecurity


@pytest.mark.asyncio
async def test_create_treasury_note(session):
    """Create a 10Y treasury note and verify fields."""
    tid = uuid.uuid4()
    note = TreasurySecurity(
        treasury_id=tid,
        cusip="912828ZT4",
        treasury_type="NOTE",
        coupon_rate=4.500000,
        coupon_frequency=2,
        issue_date=date(2025, 8, 15),
        maturity_date=date(2035, 8, 15),
        original_issue_amount=42_000_000_000.00,
        outstanding_amount=42_000_000_000.00,
        is_outstanding=True,
    )
    session.add(note)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.cusip == "912828ZT4"
    assert fetched.treasury_type == "NOTE"
    assert float(fetched.coupon_rate) == 4.5
    assert fetched.coupon_frequency == 2
    assert fetched.maturity_date == date(2035, 8, 15)
    assert fetched.is_outstanding is True


@pytest.mark.asyncio
async def test_create_treasury_bill(session):
    """Create a T-bill (coupon=0, maturity < 1Y)."""
    tid = uuid.uuid4()
    bill = TreasurySecurity(
        treasury_id=tid,
        cusip="912797GV5",
        treasury_type="BILL",
        coupon_rate=0,
        coupon_frequency=0,
        issue_date=date(2026, 1, 5),
        maturity_date=date(2026, 4, 5),
        is_outstanding=True,
    )
    session.add(bill)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.treasury_type == "BILL"
    assert float(fetched.coupon_rate) == 0
    assert fetched.coupon_frequency == 0


@pytest.mark.asyncio
async def test_create_tips(session):
    """Create a TIPS with index_ratio."""
    tid = uuid.uuid4()
    tips = TreasurySecurity(
        treasury_id=tid,
        cusip="912810SV2",
        treasury_type="TIPS",
        coupon_rate=1.750000,
        coupon_frequency=2,
        issue_date=date(2025, 1, 15),
        maturity_date=date(2035, 1, 15),
        is_inflation_indexed=True,
        index_ratio=1.02345678,
        ref_cpi_date=date(2025, 10, 1),
        ref_cpi_value=308.4170,
        is_outstanding=True,
    )
    session.add(tips)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.is_inflation_indexed is True
    assert float(fetched.index_ratio) == pytest.approx(1.02345678, abs=1e-6)
    assert fetched.ref_cpi_date == date(2025, 10, 1)


@pytest.mark.asyncio
async def test_create_strip(session):
    """Create a STRIP with stripped_from_cusip."""
    tid = uuid.uuid4()
    strip = TreasurySecurity(
        treasury_id=tid,
        cusip="912803DV1",
        treasury_type="STRIP",
        coupon_rate=0,
        coupon_frequency=0,
        issue_date=date(2025, 5, 15),
        maturity_date=date(2045, 5, 15),
        is_stripped=True,
        stripped_from_cusip="912810RZ4",
        strip_type="COUPON",
        is_outstanding=True,
    )
    session.add(strip)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.is_stripped is True
    assert fetched.stripped_from_cusip == "912810RZ4"
    assert fetched.strip_type == "COUPON"


@pytest.mark.asyncio
async def test_cusip_uniqueness(session):
    """Insert duplicate CUSIP should raise IntegrityError."""
    cusip = "912828UN6"
    session.add(TreasurySecurity(
        cusip=cusip,
        treasury_type="NOTE",
        maturity_date=date(2033, 11, 15),
    ))
    await session.flush()

    session.add(TreasurySecurity(
        cusip=cusip,
        treasury_type="NOTE",
        maturity_date=date(2034, 11, 15),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_outstanding_filter(session):
    """Create outstanding + matured securities and filter by is_outstanding."""
    session.add(TreasurySecurity(
        cusip="912828AA1",
        treasury_type="NOTE",
        maturity_date=date(2030, 6, 15),
        is_outstanding=True,
    ))
    session.add(TreasurySecurity(
        cusip="912828BB2",
        treasury_type="NOTE",
        maturity_date=date(2020, 6, 15),
        is_outstanding=False,
    ))
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.is_outstanding == True)  # noqa: E712
    )
    outstanding = result.scalars().all()
    cusips = {s.cusip for s in outstanding}
    assert "912828AA1" in cusips
    assert "912828BB2" not in cusips


@pytest.mark.asyncio
async def test_optional_fields_null(session):
    """All optional fields can be null."""
    tid = uuid.uuid4()
    minimal = TreasurySecurity(
        treasury_id=tid,
        cusip="912828CC3",
        treasury_type="NOTE",
        maturity_date=date(2035, 3, 15),
    )
    session.add(minimal)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.coupon_rate is None
    assert fetched.coupon_frequency is None
    assert fetched.issue_date is None
    assert fetched.auction_date is None
    assert fetched.index_ratio is None
    assert fetched.stripped_from_cusip is None
    assert fetched.security_id is None
    assert fetched.status is None


@pytest.mark.asyncio
async def test_status_lifecycle(session):
    """Set status to MATURED."""
    tid = uuid.uuid4()
    sec = TreasurySecurity(
        treasury_id=tid,
        cusip="912828DD4",
        treasury_type="NOTE",
        maturity_date=date(2023, 6, 15),
        is_outstanding=False,
        status="MATURED",
    )
    session.add(sec)
    await session.flush()

    result = await session.execute(
        select(TreasurySecurity).where(TreasurySecurity.treasury_id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.status == "MATURED"
    assert fetched.is_outstanding is False
