"""Tests for security master models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.security import (
    CallPutSchedule,
    CreditRating,
    EODPrice,
    EquityDetails,
    FixedIncomeDetails,
    Security,
    SecurityIdentifier,
)


@pytest.mark.asyncio
async def test_create_security(session, security_data):
    """Test creating a security record."""
    security = Security(**security_data)
    session.add(security)
    await session.flush()

    result = await session.execute(
        select(Security).where(Security.security_id == security_data["security_id"])
    )
    fetched = result.scalar_one()
    assert fetched.name == "Apple Inc. Common Stock"
    assert fetched.asset_class == "EQUITY"
    assert fetched.status == "ACTIVE"


@pytest.mark.asyncio
async def test_security_with_equity_details(session, security_data):
    """Test creating a security with equity detail record."""
    security = Security(**security_data)
    session.add(security)
    await session.flush()

    equity = EquityDetails(
        security_id=security_data["security_id"],
        shares_outstanding=15_000_000_000,
        shares_authorized=50_000_000_000,
        float_shares=14_500_000_000,
        par_value=0.00001,
        voting_rights=True,
        votes_per_share=1.0,
        dividend_frequency="QUARTERLY",
        share_class="A",
    )
    session.add(equity)
    await session.flush()

    result = await session.execute(
        select(EquityDetails).where(
            EquityDetails.security_id == security_data["security_id"]
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.shares_outstanding) == 15_000_000_000
    assert fetched.voting_rights is True


@pytest.mark.asyncio
async def test_security_with_fixed_income_details(session):
    """Test creating a fixed income security."""
    sec_id = uuid.uuid4()
    security = Security(
        security_id=sec_id,
        security_type="CORPORATE_BOND",
        name="Apple Inc. 3.25% 2026",
        status="ACTIVE",
        asset_class="FIXED_INCOME",
        issue_date=date(2021, 2, 8),
        maturity_date=date(2026, 2, 8),
    )
    session.add(security)
    await session.flush()

    fi = FixedIncomeDetails(
        security_id=sec_id,
        face_value=1000.0,
        coupon_rate=0.0325,
        coupon_type="FIXED",
        coupon_frequency="SEMI_ANNUAL",
        day_count_convention="30_360",
        seniority="SENIOR_UNSECURED",
        callable=False,
        puttable=False,
        rated=True,
    )
    session.add(fi)
    await session.flush()

    result = await session.execute(
        select(FixedIncomeDetails).where(FixedIncomeDetails.security_id == sec_id)
    )
    fetched = result.scalar_one()
    assert float(fetched.coupon_rate) == 0.0325
    assert fetched.coupon_type == "FIXED"
    assert fetched.callable is False


@pytest.mark.asyncio
async def test_security_identifiers(session, security_data):
    """Test creating multiple identifiers for a security."""
    security = Security(**security_data)
    session.add(security)
    await session.flush()

    identifiers = [
        SecurityIdentifier(
            id=uuid.uuid4(),
            security_id=security_data["security_id"],
            identifier_type="TICKER",
            identifier_value="AAPL",
            source="OPENFIGI",
        ),
        SecurityIdentifier(
            id=uuid.uuid4(),
            security_id=security_data["security_id"],
            identifier_type="ISIN",
            identifier_value="US0378331005",
            source="OPENFIGI",
        ),
        SecurityIdentifier(
            id=uuid.uuid4(),
            security_id=security_data["security_id"],
            identifier_type="FIGI",
            identifier_value="BBG000B9XRY4",
            source="OPENFIGI",
        ),
    ]
    for ident in identifiers:
        session.add(ident)
    await session.flush()

    result = await session.execute(
        select(SecurityIdentifier).where(
            SecurityIdentifier.security_id == security_data["security_id"]
        )
    )
    fetched = result.scalars().all()
    assert len(fetched) == 3


@pytest.mark.asyncio
async def test_eod_price(session, security_data):
    """Test creating EOD price records."""
    security = Security(**security_data)
    session.add(security)
    await session.flush()

    price = EODPrice(
        security_id=security_data["security_id"],
        price_date=date(2024, 12, 20),
        open=254.50,
        high=256.75,
        low=253.10,
        close=255.30,
        close_adjusted=255.30,
        volume=45_000_000,
        currency="USD",
        source="TEST",
    )
    session.add(price)
    await session.flush()

    result = await session.execute(
        select(EODPrice).where(
            EODPrice.security_id == security_data["security_id"],
            EODPrice.price_date == date(2024, 12, 20),
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.close) == 255.30
    assert float(fetched.high) >= float(fetched.low)
