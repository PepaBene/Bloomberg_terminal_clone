"""Tests for M&A deal models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.ma_deals import MandADeal


@pytest.mark.asyncio
async def test_create_deal(session):
    """Test creating an M&A deal."""
    acquirer_id = uuid.uuid4()
    target_id = uuid.uuid4()
    for eid, name in [(acquirer_id, "Acquirer Corp"), (target_id, "Target Corp")]:
        session.add(Entity(
            entity_id=eid, entity_type="PUBLIC_COMPANY",
            legal_name=name, status="ACTIVE", source="SEC_EDGAR",
        ))
    await session.flush()

    deal_id = uuid.uuid4()
    deal = MandADeal(
        deal_id=deal_id,
        acquirer_entity_id=acquirer_id,
        target_entity_id=target_id,
        acquirer_name="Acquirer Corp",
        target_name="Target Corp",
        deal_type="ACQUISITION",
        deal_status="PENDING",
        total_value=10000000000.00,
        payment_type="CASH",
        ev_to_ebitda=12.5,
        announcement_date=date(2026, 2, 15),
        primary_source="8K",
    )
    session.add(deal)
    await session.flush()

    result = await session.execute(
        select(MandADeal).where(MandADeal.deal_id == deal_id)
    )
    fetched = result.scalar_one()
    assert fetched.deal_type == "ACQUISITION"
    assert float(fetched.total_value) == 10000000000.00
    assert fetched.is_hostile is False


@pytest.mark.asyncio
async def test_deal_with_advisors(session):
    """Test storing advisory details as JSONB."""
    deal = MandADeal(
        deal_id=uuid.uuid4(),
        deal_type="MERGER_OF_EQUALS",
        deal_status="COMPLETED",
        acquirer_financial_advisors=["Goldman Sachs", "Morgan Stanley"],
        target_financial_advisors=["JP Morgan"],
        announcement_date=date(2026, 1, 10),
    )
    session.add(deal)
    await session.flush()

    result = await session.execute(
        select(MandADeal).where(MandADeal.deal_type == "MERGER_OF_EQUALS")
    )
    fetched = result.scalar_one()
    assert fetched.acquirer_financial_advisors == ["Goldman Sachs", "Morgan Stanley"]


@pytest.mark.asyncio
async def test_list_deals_by_status(session):
    """Test querying deals by status."""
    for status in ["PENDING", "COMPLETED", "PENDING"]:
        session.add(MandADeal(
            deal_id=uuid.uuid4(), deal_status=status,
            announcement_date=date(2026, 3, 1),
        ))
    await session.flush()

    result = await session.execute(
        select(MandADeal).where(MandADeal.deal_status == "PENDING")
    )
    deals = result.scalars().all()
    assert len(deals) == 2


@pytest.mark.asyncio
async def test_hostile_deal(session):
    """Test hostile deal flag."""
    deal = MandADeal(
        deal_id=uuid.uuid4(),
        deal_type="TENDER_OFFER",
        deal_status="PENDING",
        is_hostile=True,
        total_value=5000000000.00,
    )
    session.add(deal)
    await session.flush()

    result = await session.execute(
        select(MandADeal).where(MandADeal.is_hostile == True)  # noqa: E712
    )
    fetched = result.scalar_one()
    assert fetched.deal_type == "TENDER_OFFER"
