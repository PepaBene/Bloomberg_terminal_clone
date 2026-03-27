"""Tests for Agency Bond model (D11 FI Supplement P8)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.agency_bond import AgencyBond


@pytest.mark.asyncio
async def test_create_agency_bond(session):
    """Create a FNMA bond with all fields and verify persistence."""
    bid = uuid.uuid4()
    bond = AgencyBond(
        bond_id=bid,
        cusip="3136A1AA1",
        issuer_name="Federal National Mortgage Association",
        agency_type="FNMA",
        backing_type="CONSERVATORSHIP",
        coupon_rate=4.250000,
        coupon_type="FIXED",
        coupon_frequency=2,
        maturity_date=date(2034, 6, 15),
        issue_date=date(2024, 6, 15),
        original_amount_mm=5000.00,
        outstanding_amount_mm=4800.00,
        currency="USD",
        is_callable=False,
        is_outstanding=True,
        status="OUTSTANDING",
        security_id=uuid.uuid4(),
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(AgencyBond).where(AgencyBond.bond_id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.cusip == "3136A1AA1"
    assert fetched.issuer_name == "Federal National Mortgage Association"
    assert fetched.agency_type == "FNMA"
    assert fetched.backing_type == "CONSERVATORSHIP"
    assert float(fetched.coupon_rate) == pytest.approx(4.25)
    assert fetched.coupon_type == "FIXED"
    assert fetched.coupon_frequency == 2
    assert fetched.maturity_date == date(2034, 6, 15)
    assert fetched.issue_date == date(2024, 6, 15)
    assert float(fetched.original_amount_mm) == pytest.approx(5000.0)
    assert float(fetched.outstanding_amount_mm) == pytest.approx(4800.0)
    assert fetched.currency == "USD"
    assert fetched.is_callable is False
    assert fetched.is_outstanding is True
    assert fetched.status == "OUTSTANDING"
    assert fetched.security_id is not None


@pytest.mark.asyncio
async def test_cusip_uniqueness(session):
    """Insert duplicate CUSIP should raise IntegrityError."""
    cusip = "3136A1BB2"
    session.add(AgencyBond(
        cusip=cusip,
        agency_type="FNMA",
        maturity_date=date(2030, 6, 15),
    ))
    await session.flush()

    session.add(AgencyBond(
        cusip=cusip,
        agency_type="FHLMC",
        maturity_date=date(2031, 6, 15),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_agency_types(session):
    """Create bonds for each agency type."""
    types = ["FNMA", "FHLMC", "FHLB", "FFCB", "TVA", "SBA", "GNMA"]
    for i, atype in enumerate(types):
        session.add(AgencyBond(
            cusip=f"AGTYP{i:04d}",
            agency_type=atype,
            maturity_date=date(2030, 1, 1),
        ))
    await session.flush()

    result = await session.execute(select(AgencyBond).where(
        AgencyBond.cusip.like("AGTYP%")
    ))
    bonds = result.scalars().all()
    found_types = {b.agency_type for b in bonds}
    assert found_types == set(types)


@pytest.mark.asyncio
async def test_backing_types(session):
    """Test each backing type value."""
    backing_types = ["EXPLICIT_GUARANTEE", "CONSERVATORSHIP", "IMPLICIT_SUPPORT"]
    for i, btype in enumerate(backing_types):
        session.add(AgencyBond(
            cusip=f"BKTYP{i:04d}",
            agency_type="GNMA",
            backing_type=btype,
            maturity_date=date(2032, 3, 15),
        ))
    await session.flush()

    result = await session.execute(select(AgencyBond).where(
        AgencyBond.cusip.like("BKTYP%")
    ))
    bonds = result.scalars().all()
    found_backing = {b.backing_type for b in bonds}
    assert found_backing == set(backing_types)


@pytest.mark.asyncio
async def test_callable_bond(session):
    """Create callable bond with first_call_date."""
    bid = uuid.uuid4()
    bond = AgencyBond(
        bond_id=bid,
        cusip="3136CALL1",
        agency_type="FHLB",
        coupon_rate=3.500000,
        coupon_type="FIXED",
        maturity_date=date(2034, 9, 15),
        is_callable=True,
        first_call_date=date(2029, 9, 15),
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(AgencyBond).where(AgencyBond.bond_id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.is_callable is True
    assert fetched.first_call_date == date(2029, 9, 15)


@pytest.mark.asyncio
async def test_outstanding_filter(session):
    """Filter by is_outstanding."""
    session.add(AgencyBond(
        cusip="AGOUT0001",
        agency_type="FNMA",
        maturity_date=date(2035, 6, 15),
        is_outstanding=True,
    ))
    session.add(AgencyBond(
        cusip="AGOUT0002",
        agency_type="FNMA",
        maturity_date=date(2020, 6, 15),
        is_outstanding=False,
    ))
    await session.flush()

    result = await session.execute(
        select(AgencyBond).where(AgencyBond.is_outstanding == True)  # noqa: E712
    )
    outstanding = result.scalars().all()
    cusips = {b.cusip for b in outstanding}
    assert "AGOUT0001" in cusips
    assert "AGOUT0002" not in cusips


@pytest.mark.asyncio
async def test_floating_rate(session):
    """Create a floating-rate agency bond."""
    bid = uuid.uuid4()
    bond = AgencyBond(
        bond_id=bid,
        cusip="3136FLT01",
        agency_type="FHLMC",
        coupon_rate=0.0,
        coupon_type="FLOATING",
        coupon_frequency=4,
        maturity_date=date(2027, 3, 15),
        is_outstanding=True,
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(AgencyBond).where(AgencyBond.bond_id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.coupon_type == "FLOATING"
    assert fetched.coupon_frequency == 4


@pytest.mark.asyncio
async def test_nullable_fields(session):
    """Minimal creation with only required fields."""
    bid = uuid.uuid4()
    bond = AgencyBond(
        bond_id=bid,
        cusip="3136MIN01",
        maturity_date=date(2030, 12, 31),
    )
    session.add(bond)
    await session.flush()

    result = await session.execute(
        select(AgencyBond).where(AgencyBond.bond_id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.issuer_name is None
    assert fetched.agency_type is None
    assert fetched.backing_type is None
    assert fetched.coupon_rate is None
    assert fetched.coupon_type is None
    assert fetched.coupon_frequency is None
    assert fetched.issue_date is None
    assert fetched.original_amount_mm is None
    assert fetched.outstanding_amount_mm is None
    assert fetched.currency is None
    assert fetched.first_call_date is None
    assert fetched.status is None
    assert fetched.security_id is None
