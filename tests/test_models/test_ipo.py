"""Tests for IPO event models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.ipo import IPOEvent


@pytest.mark.asyncio
async def test_create_ipo_event(session):
    """Test creating an IPO event."""
    ipo_id = uuid.uuid4()
    ipo = IPOEvent(
        ipo_id=ipo_id,
        s1_filing_date=date(2026, 1, 15),
        pricing_date=date(2026, 3, 1),
        trading_start_date=date(2026, 3, 2),
        offer_price=25.00,
        shares_offered=10000000,
        total_proceeds=250000000.00,
        first_day_close=32.50,
        first_day_return_pct=0.30,
        lead_underwriters=["Goldman Sachs", "JP Morgan"],
        gics_sector="Information Technology",
        status="TRADING",
    )
    session.add(ipo)
    await session.flush()

    result = await session.execute(
        select(IPOEvent).where(IPOEvent.ipo_id == ipo_id)
    )
    fetched = result.scalar_one()
    assert float(fetched.offer_price) == 25.00
    assert float(fetched.first_day_return_pct) == pytest.approx(0.30, abs=0.01)
    assert fetched.status == "TRADING"


@pytest.mark.asyncio
async def test_ipo_pipeline(session):
    """Test querying IPOs in pipeline status."""
    for status in ["FILED", "AMENDED", "PRICED", "TRADING"]:
        session.add(IPOEvent(
            ipo_id=uuid.uuid4(),
            status=status,
            s1_filing_date=date(2026, 2, 1),
        ))
    await session.flush()

    result = await session.execute(
        select(IPOEvent).where(IPOEvent.status.in_(["FILED", "AMENDED"]))
    )
    ipos = result.scalars().all()
    assert len(ipos) == 2


@pytest.mark.asyncio
async def test_ipo_withdrawn(session):
    """Test withdrawn IPO with reason."""
    ipo = IPOEvent(
        ipo_id=uuid.uuid4(),
        status="WITHDRAWN",
        withdrawal_date=date(2026, 3, 15),
        withdrawal_reason="Market conditions",
    )
    session.add(ipo)
    await session.flush()

    result = await session.execute(
        select(IPOEvent).where(IPOEvent.status == "WITHDRAWN")
    )
    fetched = result.scalar_one()
    assert fetched.withdrawal_reason == "Market conditions"
