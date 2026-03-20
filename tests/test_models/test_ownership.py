"""Tests for ownership models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.ownership import (
    InsiderHolding,
    InstitutionalHolding,
    InstitutionProfile,
    OwnershipSummary,
    ShortInterest,
)


@pytest.mark.asyncio
async def test_create_institution_profile(session):
    """Test creating an institution profile."""
    institution_id = uuid.uuid4()
    profile = InstitutionProfile(
        institution_id=institution_id,
        institution_name="Vanguard Group Inc.",
        institution_type="PASSIVE_INDEX",
        tier="WHALE",
        aum=Decimal("8500000000000.00"),
        number_of_holdings=4200,
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(InstitutionProfile).where(
            InstitutionProfile.institution_id == institution_id
        )
    )
    fetched = result.scalar_one()
    assert fetched.institution_name == "Vanguard Group Inc."
    assert fetched.institution_type == "PASSIVE_INDEX"
    assert fetched.tier == "WHALE"
    assert fetched.number_of_holdings == 4200


@pytest.mark.asyncio
async def test_create_institutional_holding(session, security_data):
    """Test creating an institutional holding record."""
    from src.models.security import Security

    security = Security(**security_data)
    session.add(security)
    await session.flush()

    institution_id = uuid.uuid4()
    profile = InstitutionProfile(
        institution_id=institution_id,
        institution_name="BlackRock Inc.",
        institution_type="PASSIVE_INDEX",
        tier="WHALE",
    )
    session.add(profile)
    await session.flush()

    holding = InstitutionalHolding(
        institution_id=institution_id,
        security_id=security_data["security_id"],
        report_date=date(2024, 9, 30),
        filing_date=date(2024, 11, 14),
        shares_held=Decimal("1200000000.00"),
        market_value=Decimal("270000000000.00"),
        percent_of_portfolio=Decimal("5.2300"),
        percent_of_outstanding=Decimal("7.8100"),
        shares_change=Decimal("15000000.00"),
        is_new_position=False,
        is_sold_out=False,
        source="SEC_13F",
    )
    session.add(holding)
    await session.flush()

    result = await session.execute(
        select(InstitutionalHolding).where(
            InstitutionalHolding.institution_id == institution_id,
            InstitutionalHolding.security_id == security_data["security_id"],
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.shares_held) == 1200000000.00
    assert float(fetched.percent_of_outstanding) == 7.81


@pytest.mark.asyncio
async def test_create_insider_holding(session, security_data):
    """Test creating an insider transaction record."""
    from src.models.security import Security

    security = Security(**security_data)
    session.add(security)
    await session.flush()

    transaction_id = uuid.uuid4()
    insider = InsiderHolding(
        transaction_id=transaction_id,
        security_id=security_data["security_id"],
        insider_name="Tim Cook",
        insider_title="CEO",
        insider_relationship="OFFICER",
        transaction_type="SALE",
        transaction_date=date(2024, 10, 1),
        shares_transacted=Decimal("75000.00"),
        price_per_share=Decimal("226.210000"),
        total_value=Decimal("16965750.00"),
        shares_owned_after=Decimal("3280557.00"),
        ownership_nature="DIRECT",
    )
    session.add(insider)
    await session.flush()

    result = await session.execute(
        select(InsiderHolding).where(
            InsiderHolding.transaction_id == transaction_id
        )
    )
    fetched = result.scalar_one()
    assert fetched.insider_name == "Tim Cook"
    assert fetched.transaction_type == "SALE"
    assert float(fetched.price_per_share) == 226.21


@pytest.mark.asyncio
async def test_create_ownership_summary(session, security_data):
    """Test creating an ownership summary record."""
    from src.models.security import Security

    security = Security(**security_data)
    session.add(security)
    await session.flush()

    summary = OwnershipSummary(
        security_id=security_data["security_id"],
        report_date=date(2024, 9, 30),
        institutional_holders_count=5200,
        institutional_shares=Decimal("11500000000.00"),
        insider_shares=Decimal("450000000.00"),
        institutional_percent=Decimal("74.5200"),
        insider_percent=Decimal("2.9100"),
        top_10_concentration=Decimal("35.4000"),
    )
    session.add(summary)
    await session.flush()

    result = await session.execute(
        select(OwnershipSummary).where(
            OwnershipSummary.security_id == security_data["security_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.institutional_holders_count == 5200
    assert float(fetched.institutional_percent) == 74.52
    assert float(fetched.top_10_concentration) == 35.40


@pytest.mark.asyncio
async def test_create_short_interest(session, security_data):
    """Test creating a short interest record."""
    from src.models.security import Security

    security = Security(**security_data)
    session.add(security)
    await session.flush()

    short = ShortInterest(
        security_id=security_data["security_id"],
        settlement_date=date(2024, 10, 15),
        shares_short=Decimal("120000000.00"),
        short_percent_float=Decimal("0.9800"),
        short_percent_outstanding=Decimal("0.7800"),
        days_to_cover=Decimal("1.20"),
        source="FINRA",
    )
    session.add(short)
    await session.flush()

    result = await session.execute(
        select(ShortInterest).where(
            ShortInterest.security_id == security_data["security_id"]
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.shares_short) == 120000000.00
    assert float(fetched.days_to_cover) == 1.20
    assert fetched.source == "FINRA"
