"""Tests for company fundamentals models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    Filing,
    FinancialPeriod,
    IncomeStatement,
    SegmentData,
)


@pytest.fixture
def filing_data(entity_data):
    """Sample filing data."""
    return {
        "filing_id": uuid.uuid4(),
        "entity_id": entity_data["entity_id"],
        "filing_type": "10-K",
        "accession_number": "0000320193-24-000123",
        "filing_date": date(2024, 11, 1),
        "period_end_date": date(2024, 9, 30),
        "fiscal_year": 2024,
        "fiscal_quarter": None,
        "period_type": "ANNUAL",
        "processing_status": "PROCESSED",
        "source": "SEC_EDGAR",
    }


@pytest.fixture
def period_data(entity_data):
    """Sample financial period data."""
    return {
        "period_id": uuid.uuid4(),
        "entity_id": entity_data["entity_id"],
        "period_end_date": date(2024, 9, 30),
        "period_type": "ANNUAL",
        "fiscal_year": 2024,
        "data_version": "AS_REPORTED",
    }


@pytest.mark.asyncio
async def test_create_filing(session, entity_data, filing_data):
    """Test creating a filing record."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    filing = Filing(**filing_data)
    session.add(filing)
    await session.flush()

    result = await session.execute(
        select(Filing).where(Filing.filing_id == filing_data["filing_id"])
    )
    fetched = result.scalar_one()
    assert fetched.filing_type == "10-K"
    assert fetched.accession_number == "0000320193-24-000123"
    assert fetched.fiscal_year == 2024


@pytest.mark.asyncio
async def test_create_financial_period(session, entity_data, period_data):
    """Test creating a financial period."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(**period_data)
    session.add(period)
    await session.flush()

    result = await session.execute(
        select(FinancialPeriod).where(
            FinancialPeriod.period_id == period_data["period_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.period_type == "ANNUAL"
    assert fetched.fiscal_year == 2024


@pytest.mark.asyncio
async def test_create_income_statement(session, entity_data, period_data):
    """Test creating an income statement linked to a period."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(**period_data)
    session.add(period)
    await session.flush()

    statement = IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=period_data["period_id"],
        total_revenue=Decimal("391035000000.00"),
        cost_of_revenue=Decimal("214137000000.00"),
        gross_profit=Decimal("176898000000.00"),
        operating_income=Decimal("123216000000.00"),
        net_income=Decimal("93736000000.00"),
        basic_eps=Decimal("6.13"),
        diluted_eps=Decimal("6.08"),
    )
    session.add(statement)
    await session.flush()

    result = await session.execute(
        select(IncomeStatement).where(
            IncomeStatement.period_id == period_data["period_id"]
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.total_revenue) == 391035000000.00
    assert float(fetched.diluted_eps) == 6.08


@pytest.mark.asyncio
async def test_create_balance_sheet(session, entity_data, period_data):
    """Test creating a balance sheet."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(**period_data)
    session.add(period)
    await session.flush()

    bs = BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=period_data["period_id"],
        total_assets=Decimal("352583000000.00"),
        total_liabilities=Decimal("290437000000.00"),
        total_equity=Decimal("62146000000.00"),
        total_liabilities_and_equity=Decimal("352583000000.00"),
        cash_and_equivalents=Decimal("29965000000.00"),
        total_debt=Decimal("106629000000.00"),
    )
    session.add(bs)
    await session.flush()

    result = await session.execute(
        select(BalanceSheet).where(BalanceSheet.period_id == period_data["period_id"])
    )
    fetched = result.scalar_one()
    assert float(fetched.total_assets) == 352583000000.00
    assert float(fetched.total_equity) == 62146000000.00


@pytest.mark.asyncio
async def test_create_cash_flow(session, entity_data, period_data):
    """Test creating a cash flow statement."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(**period_data)
    session.add(period)
    await session.flush()

    cf = CashFlowStatement(
        statement_id=uuid.uuid4(),
        period_id=period_data["period_id"],
        cash_from_operations=Decimal("118254000000.00"),
        capital_expenditures=Decimal("-9959000000.00"),
        cash_from_investing=Decimal("-22234000000.00"),
        cash_from_financing=Decimal("-96790000000.00"),
        free_cash_flow=Decimal("108295000000.00"),
        dividends_paid=Decimal("-15234000000.00"),
    )
    session.add(cf)
    await session.flush()

    result = await session.execute(
        select(CashFlowStatement).where(
            CashFlowStatement.period_id == period_data["period_id"]
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.cash_from_operations) == 118254000000.00
    assert float(fetched.free_cash_flow) == 108295000000.00


@pytest.mark.asyncio
async def test_create_segment(session, entity_data, period_data):
    """Test creating segment data."""
    from src.models.entity import Entity

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(**period_data)
    session.add(period)
    await session.flush()

    segment = SegmentData(
        segment_id=uuid.uuid4(),
        period_id=period_data["period_id"],
        entity_id=entity_data["entity_id"],
        segment_type="PRODUCT",
        segment_name="iPhone",
        revenue=Decimal("200583000000.00"),
        operating_income=Decimal("90000000000.00"),
        operating_margin=Decimal("0.4489"),
    )
    session.add(segment)
    await session.flush()

    result = await session.execute(
        select(SegmentData).where(SegmentData.entity_id == entity_data["entity_id"])
    )
    fetched = result.scalar_one()
    assert fetched.segment_name == "iPhone"
    assert fetched.segment_type == "PRODUCT"
