"""Tests for macroeconomic data models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.macro import CentralBankPolicy, MacroIndicator, MacroValue


@pytest.fixture
def indicator_data():
    """Sample macro indicator data."""
    return {
        "indicator_id": uuid.uuid4(),
        "indicator_code": "GDP",
        "name": "Gross Domestic Product",
        "short_name": "GDP",
        "category": "GDP",
        "country_code": "US",
        "frequency": "QUARTERLY",
        "unit": "Billions of Dollars",
        "seasonal_adjustment": "SAAR",
        "source_agency": "Federal Reserve Economic Data (FRED)",
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_create_macro_indicator(session, indicator_data):
    """Test creating a macro indicator."""
    indicator = MacroIndicator(**indicator_data)
    session.add(indicator)
    await session.flush()

    result = await session.execute(
        select(MacroIndicator).where(
            MacroIndicator.indicator_id == indicator_data["indicator_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.indicator_code == "GDP"
    assert fetched.name == "Gross Domestic Product"
    assert fetched.category == "GDP"
    assert fetched.frequency == "QUARTERLY"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_macro_indicator_unique_code(session, indicator_data):
    """Test that indicator_code must be unique."""
    indicator1 = MacroIndicator(**indicator_data)
    session.add(indicator1)
    await session.flush()

    # Verify it was created
    result = await session.execute(
        select(MacroIndicator).where(MacroIndicator.indicator_code == "GDP")
    )
    assert result.scalar_one() is not None


@pytest.mark.asyncio
async def test_create_macro_value(session, indicator_data):
    """Test creating a macro value linked to an indicator."""
    indicator = MacroIndicator(**indicator_data)
    session.add(indicator)
    await session.flush()

    value = MacroValue(
        indicator_id=indicator_data["indicator_id"],
        observation_date=date(2024, 1, 1),
        vintage_date=date(2024, 3, 28),
        value=Decimal("28269.5"),
        period_type="QUARTERLY",
        revision_number=0,
        is_preliminary=False,
        is_revised=False,
        source="FRED",
    )
    session.add(value)
    await session.flush()

    result = await session.execute(
        select(MacroValue).where(
            MacroValue.indicator_id == indicator_data["indicator_id"],
            MacroValue.observation_date == date(2024, 1, 1),
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.value) == 28269.5
    assert fetched.source == "FRED"
    assert fetched.revision_number == 0


@pytest.mark.asyncio
async def test_macro_value_with_transforms(session, indicator_data):
    """Test macro values with pre-computed transformations."""
    indicator = MacroIndicator(**indicator_data)
    session.add(indicator)
    await session.flush()

    value = MacroValue(
        indicator_id=indicator_data["indicator_id"],
        observation_date=date(2024, 4, 1),
        vintage_date=date(2024, 6, 27),
        value=Decimal("28800.0"),
        value_yoy=Decimal("1500.0"),
        value_yoy_percent=Decimal("5.5"),
        value_mom=Decimal("530.5"),
        value_mom_percent=Decimal("1.88"),
        previous_value=Decimal("28269.5"),
        source="FRED",
    )
    session.add(value)
    await session.flush()

    result = await session.execute(
        select(MacroValue).where(
            MacroValue.indicator_id == indicator_data["indicator_id"],
            MacroValue.observation_date == date(2024, 4, 1),
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.value_yoy_percent) == 5.5
    assert float(fetched.previous_value) == 28269.5


@pytest.mark.asyncio
async def test_create_central_bank_policy(session):
    """Test creating a central bank policy record."""
    policy = CentralBankPolicy(
        policy_id=uuid.uuid4(),
        bank_code="FED",
        meeting_date=date(2024, 3, 20),
        decision_date=date(2024, 3, 20),
        policy_rate=Decimal("5.5000"),
        rate_change=Decimal("0.0000"),
        previous_rate=Decimal("5.5000"),
        rate_direction="HOLD",
        votes_for=12,
        votes_against=0,
        guidance_tone="NEUTRAL",
        statement_summary="Maintained target range at 5.25-5.50 percent.",
        source="FED",
    )
    session.add(policy)
    await session.flush()

    result = await session.execute(
        select(CentralBankPolicy).where(
            CentralBankPolicy.bank_code == "FED",
            CentralBankPolicy.meeting_date == date(2024, 3, 20),
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.policy_rate) == 5.5
    assert fetched.rate_direction == "HOLD"
    assert fetched.votes_for == 12


@pytest.mark.asyncio
async def test_central_bank_rate_change(session):
    """Test central bank policy with a rate change."""
    policy = CentralBankPolicy(
        policy_id=uuid.uuid4(),
        bank_code="FED",
        meeting_date=date(2024, 9, 18),
        decision_date=date(2024, 9, 18),
        policy_rate=Decimal("5.0000"),
        rate_change=Decimal("-0.5000"),
        previous_rate=Decimal("5.5000"),
        rate_direction="CUT",
        votes_for=11,
        votes_against=1,
        guidance_tone="DOVISH",
        source="FED",
    )
    session.add(policy)
    await session.flush()

    result = await session.execute(
        select(CentralBankPolicy).where(
            CentralBankPolicy.meeting_date == date(2024, 9, 18),
        )
    )
    fetched = result.scalar_one()
    assert fetched.rate_direction == "CUT"
    assert float(fetched.rate_change) == -0.5
    assert fetched.votes_against == 1


@pytest.mark.asyncio
async def test_multiple_macro_values(session, indicator_data):
    """Test creating multiple values for the same indicator."""
    indicator = MacroIndicator(**indicator_data)
    session.add(indicator)
    await session.flush()

    dates = [date(2024, 1, 1), date(2024, 4, 1), date(2024, 7, 1)]
    gdp_values = [Decimal("28269.5"), Decimal("28800.0"), Decimal("29200.0")]

    for obs_date, val in zip(dates, gdp_values):
        value = MacroValue(
            indicator_id=indicator_data["indicator_id"],
            observation_date=obs_date,
            vintage_date=obs_date,
            value=val,
            source="FRED",
        )
        session.add(value)
    await session.flush()

    result = await session.execute(
        select(MacroValue)
        .where(MacroValue.indicator_id == indicator_data["indicator_id"])
        .order_by(MacroValue.observation_date)
    )
    values = result.scalars().all()
    assert len(values) == 3
    assert float(values[0].value) == 28269.5
    assert float(values[2].value) == 29200.0
