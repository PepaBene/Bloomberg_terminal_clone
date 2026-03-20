"""Tests for reference data models."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.models.reference import Country, Currency, Exchange, GICSClassification


@pytest.mark.asyncio
async def test_create_currency(session, currency_data):
    """Test creating a currency record."""
    currency = Currency(**currency_data)
    session.add(currency)
    await session.flush()

    result = await session.execute(
        select(Currency).where(Currency.currency_code == "USD")
    )
    fetched = result.scalar_one()
    assert fetched.currency_code == "USD"
    assert fetched.name == "US Dollar"
    assert fetched.minor_unit == 2
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_create_country(session, currency_data, country_data):
    """Test creating a country with currency FK."""
    session.add(Currency(**currency_data))
    await session.flush()

    country = Country(**country_data)
    session.add(country)
    await session.flush()

    result = await session.execute(
        select(Country).where(Country.country_code_alpha2 == "US")
    )
    fetched = result.scalar_one()
    assert fetched.name == "United States"
    assert fetched.currency_code == "USD"
    assert fetched.development_status == "DEVELOPED"


@pytest.mark.asyncio
async def test_create_exchange(session, currency_data, country_data):
    """Test creating an exchange with country FK."""
    session.add(Currency(**currency_data))
    await session.flush()
    session.add(Country(**country_data))
    await session.flush()

    exchange = Exchange(
        mic="XNYS",
        name="New York Stock Exchange",
        acronym="NYSE",
        country="US",
        city="New York",
        timezone="America/New_York",
        market_type="STOCK",
        status="ACTIVE",
        trading_hours={"open": "09:30", "close": "16:00"},
    )
    session.add(exchange)
    await session.flush()

    result = await session.execute(
        select(Exchange).where(Exchange.mic == "XNYS")
    )
    fetched = result.scalar_one()
    assert fetched.name == "New York Stock Exchange"
    assert fetched.country == "US"


@pytest.mark.asyncio
async def test_create_gics(session):
    """Test creating a GICS classification."""
    gics = GICSClassification(
        sub_industry_code="45101010",
        sector_code="45",
        sector_name="Information Technology",
        industry_group_code="4510",
        industry_group_name="Software & Services",
        industry_code="451010",
        industry_name="IT Services",
        sub_industry_name="IT Consulting & Other Services",
    )
    session.add(gics)
    await session.flush()

    result = await session.execute(
        select(GICSClassification).where(
            GICSClassification.sub_industry_code == "45101010"
        )
    )
    fetched = result.scalar_one()
    assert fetched.sector_name == "Information Technology"
