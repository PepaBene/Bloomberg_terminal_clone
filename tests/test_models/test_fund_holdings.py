"""Tests for fund holdings models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.fund_holdings import Fund, FundHolding


@pytest.mark.asyncio
async def test_create_fund(session):
    """Test creating a fund."""
    fund_id = uuid.uuid4()
    fund = Fund(
        fund_id=fund_id,
        fund_name="Vanguard Total Stock Market ETF",
        fund_ticker="VTI",
        fund_type="ETF",
        total_net_assets=350000000000.00,
        number_of_holdings=3950,
        top_10_concentration=0.2850,
        expense_ratio=0.0003,
    )
    session.add(fund)
    await session.flush()

    result = await session.execute(select(Fund).where(Fund.fund_id == fund_id))
    fetched = result.scalar_one()
    assert fetched.fund_ticker == "VTI"
    assert fetched.number_of_holdings == 3950


@pytest.mark.asyncio
async def test_create_fund_holding(session):
    """Test creating fund holdings."""
    fund_id = uuid.uuid4()
    fund = Fund(fund_id=fund_id, fund_name="Test ETF", fund_type="ETF")
    session.add(fund)
    await session.flush()

    holding = FundHolding(
        holding_id=uuid.uuid4(),
        fund_id=fund_id,
        report_date=date(2025, 12, 31),
        security_name="Apple Inc.",
        cusip="037833100",
        quantity=150000000,
        market_value=35000000000.00,
        pct_of_nav=0.0725,
        asset_type="EQUITY",
    )
    session.add(holding)
    await session.flush()

    result = await session.execute(
        select(FundHolding).where(FundHolding.fund_id == fund_id)
    )
    fetched = result.scalar_one()
    assert fetched.security_name == "Apple Inc."
    assert float(fetched.pct_of_nav) == pytest.approx(0.0725, abs=0.001)


@pytest.mark.asyncio
async def test_list_holdings_by_fund(session):
    """Test querying holdings by fund."""
    fund_id = uuid.uuid4()
    fund = Fund(fund_id=fund_id, fund_name="Multi-Holding ETF", fund_type="ETF")
    session.add(fund)
    await session.flush()

    for i, name in enumerate(["Apple Inc.", "Microsoft Corp.", "Amazon.com Inc."]):
        session.add(FundHolding(
            holding_id=uuid.uuid4(),
            fund_id=fund_id,
            report_date=date(2025, 12, 31),
            security_name=name,
            pct_of_nav=0.07 - i * 0.01,
            asset_type="EQUITY",
        ))
    await session.flush()

    result = await session.execute(
        select(FundHolding).where(FundHolding.fund_id == fund_id)
    )
    holdings = result.scalars().all()
    assert len(holdings) == 3


@pytest.mark.asyncio
async def test_fund_types(session):
    """Test querying funds by type."""
    for ftype, name in [("ETF", "ETF Fund"), ("MUTUAL_FUND", "Mutual Fund"), ("ETF", "Another ETF")]:
        session.add(Fund(fund_id=uuid.uuid4(), fund_name=name, fund_type=ftype))
    await session.flush()

    result = await session.execute(select(Fund).where(Fund.fund_type == "ETF"))
    funds = result.scalars().all()
    assert len(funds) == 2
