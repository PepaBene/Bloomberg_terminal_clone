"""Tests for corporate actions models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.corporate_actions import (
    CorporateAction,
    DividendAction,
    MergerAcquisitionAction,
    SplitAction,
)
from src.models.entity import Entity
from src.models.security import Security


@pytest.mark.asyncio
async def test_create_corporate_action(session):
    """Test creating a basic corporate action."""
    action_id = uuid.uuid4()
    action = CorporateAction(
        action_id=action_id,
        action_type="CASH_DIVIDEND",
        status="ANNOUNCED",
        announcement_date=date(2026, 3, 1),
        ex_date=date(2026, 3, 15),
        record_date=date(2026, 3, 16),
        payment_date=date(2026, 3, 30),
        description="Quarterly cash dividend",
        source="EXCHANGE_FEED",
    )
    session.add(action)
    await session.flush()

    result = await session.execute(
        select(CorporateAction).where(CorporateAction.action_id == action_id)
    )
    fetched = result.scalar_one()
    assert fetched.action_type == "CASH_DIVIDEND"
    assert fetched.status == "ANNOUNCED"
    assert fetched.ex_date == date(2026, 3, 15)


@pytest.mark.asyncio
async def test_create_dividend_action(session):
    """Test creating a dividend action linked to a corporate action."""
    action_id = uuid.uuid4()
    action = CorporateAction(
        action_id=action_id,
        action_type="CASH_DIVIDEND",
        status="CONFIRMED",
        ex_date=date(2026, 4, 1),
        source="EXCHANGE_FEED",
    )
    session.add(action)
    await session.flush()

    dividend = DividendAction(
        action_id=action_id,
        dividend_type="REGULAR",
        frequency="QUARTERLY",
        gross_amount=0.82,
        currency="USD",
        tax_rate=0.15,
        qualified=True,
    )
    session.add(dividend)
    await session.flush()

    result = await session.execute(
        select(DividendAction).where(DividendAction.action_id == action_id)
    )
    fetched = result.scalar_one()
    assert fetched.dividend_type == "REGULAR"
    assert float(fetched.gross_amount) == 0.82
    assert fetched.qualified is True


@pytest.mark.asyncio
async def test_create_split_action(session):
    """Test creating a stock split action."""
    action_id = uuid.uuid4()
    action = CorporateAction(
        action_id=action_id,
        action_type="STOCK_SPLIT",
        status="COMPLETED",
        ex_date=date(2026, 6, 15),
        source="EXCHANGE_FEED",
    )
    session.add(action)
    await session.flush()

    split = SplitAction(
        action_id=action_id,
        split_ratio_from=1,
        split_ratio_to=4,
        split_factor=4.0,
        adjustment_factor=0.25,
    )
    session.add(split)
    await session.flush()

    result = await session.execute(
        select(SplitAction).where(SplitAction.action_id == action_id)
    )
    fetched = result.scalar_one()
    assert fetched.split_ratio_from == 1
    assert fetched.split_ratio_to == 4
    assert float(fetched.split_factor) == 4.0


@pytest.mark.asyncio
async def test_create_ma_action(session):
    """Test creating a merger & acquisition action."""
    # Create acquirer and target entities
    acquirer_id = uuid.uuid4()
    target_id = uuid.uuid4()
    acquirer = Entity(
        entity_id=acquirer_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Big Corp Inc.",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    target = Entity(
        entity_id=target_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Small Corp Inc.",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(acquirer)
    session.add(target)
    await session.flush()

    action_id = uuid.uuid4()
    action = CorporateAction(
        action_id=action_id,
        action_type="MERGER",
        status="ANNOUNCED",
        announcement_date=date(2026, 2, 1),
        source="EXCHANGE_FEED",
    )
    session.add(action)
    await session.flush()

    ma = MergerAcquisitionAction(
        action_id=action_id,
        transaction_type="ACQUISITION",
        acquirer_entity_id=acquirer_id,
        target_entity_id=target_id,
        deal_value=5000000000.00,
        deal_currency="USD",
        price_per_share=45.50,
        consideration_type="ALL_CASH",
        premium_1day=25.5,
        premium_30day=30.2,
    )
    session.add(ma)
    await session.flush()

    result = await session.execute(
        select(MergerAcquisitionAction).where(
            MergerAcquisitionAction.action_id == action_id
        )
    )
    fetched = result.scalar_one()
    assert fetched.transaction_type == "ACQUISITION"
    assert fetched.acquirer_entity_id == acquirer_id
    assert fetched.target_entity_id == target_id
    assert float(fetched.deal_value) == 5000000000.00


@pytest.mark.asyncio
async def test_list_corporate_actions(session):
    """Test listing corporate actions filtered by security."""
    sec_id = uuid.uuid4()
    security = Security(
        security_id=sec_id,
        security_type="COMMON_STOCK",
        name="Test Corp Common Stock",
        status="ACTIVE",
        asset_class="EQUITY",
    )
    session.add(security)
    await session.flush()

    # Create two actions for this security
    for i, atype in enumerate(["CASH_DIVIDEND", "STOCK_SPLIT"]):
        action = CorporateAction(
            action_id=uuid.uuid4(),
            action_type=atype,
            security_id=sec_id,
            status="COMPLETED",
            ex_date=date(2026, 1 + i, 15),
            source="EXCHANGE_FEED",
        )
        session.add(action)
    await session.flush()

    result = await session.execute(
        select(CorporateAction).where(CorporateAction.security_id == sec_id)
    )
    actions = result.scalars().all()
    assert len(actions) == 2
    action_types = {a.action_type for a in actions}
    assert "CASH_DIVIDEND" in action_types
    assert "STOCK_SPLIT" in action_types
