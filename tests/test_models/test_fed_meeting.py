"""Tests for Fed meeting and money market rate models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.fed_meeting import FedMeeting, MoneyMarketRate


@pytest.mark.asyncio
async def test_create_fed_meeting(session):
    """Test creating an FOMC meeting record."""
    meeting_id = uuid.uuid4()
    meeting = FedMeeting(
        meeting_id=meeting_id,
        meeting_date=date(2026, 3, 19),
        meeting_type="SCHEDULED",
        rate_decision="HOLD",
        fed_funds_lower=0.0525,
        fed_funds_upper=0.0550,
        change_bps=0,
        statement_text="The Committee decided to maintain the target range...",
    )
    session.add(meeting)
    await session.flush()

    result = await session.execute(
        select(FedMeeting).where(FedMeeting.meeting_id == meeting_id)
    )
    fetched = result.scalar_one()
    assert fetched.rate_decision == "HOLD"
    assert fetched.change_bps == 0
    assert float(fetched.fed_funds_upper) == pytest.approx(0.0550, abs=0.0001)


@pytest.mark.asyncio
async def test_list_fed_meetings(session):
    """Test querying multiple FOMC meetings."""
    for i, (d, decision, bps) in enumerate([
        (date(2026, 1, 29), "HOLD", 0),
        (date(2026, 3, 19), "CUT", -25),
        (date(2026, 5, 7), "HOLD", 0),
    ]):
        session.add(FedMeeting(
            meeting_id=uuid.uuid4(),
            meeting_date=d,
            meeting_type="SCHEDULED",
            rate_decision=decision,
            change_bps=bps,
        ))
    await session.flush()

    result = await session.execute(
        select(FedMeeting).order_by(FedMeeting.meeting_date.asc())
    )
    meetings = result.scalars().all()
    assert len(meetings) == 3
    assert meetings[1].rate_decision == "CUT"
    assert meetings[1].change_bps == -25


@pytest.mark.asyncio
async def test_create_money_market_rate(session):
    """Test creating a money market rate observation."""
    rate_id = uuid.uuid4()
    rate = MoneyMarketRate(
        id=rate_id,
        rate_date=date(2026, 3, 19),
        rate_type="SOFR",
        rate_value=0.0533,
        source="FRED",
    )
    session.add(rate)
    await session.flush()

    result = await session.execute(
        select(MoneyMarketRate).where(MoneyMarketRate.id == rate_id)
    )
    fetched = result.scalar_one()
    assert fetched.rate_type == "SOFR"
    assert float(fetched.rate_value) == pytest.approx(0.0533, abs=0.0001)


@pytest.mark.asyncio
async def test_list_money_market_rates(session):
    """Test querying money market rates by type."""
    for rtype in ["SOFR", "FED_FUNDS_EFFECTIVE", "PRIME"]:
        session.add(MoneyMarketRate(
            id=uuid.uuid4(),
            rate_date=date(2026, 3, 19),
            rate_type=rtype,
            rate_value=0.05,
        ))
    await session.flush()

    result = await session.execute(
        select(MoneyMarketRate).where(MoneyMarketRate.rate_type == "SOFR")
    )
    rates = result.scalars().all()
    assert len(rates) == 1
    assert rates[0].rate_type == "SOFR"
