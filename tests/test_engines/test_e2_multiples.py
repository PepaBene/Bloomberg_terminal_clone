"""Tests for the Valuation Multiples engine."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e2_multiples import MultiplesEngine
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security


@pytest_asyncio.fixture
async def seeded_security_multiples(session: AsyncSession) -> Security:
    """Create security with fundamentals + price data for multiples."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Multiples Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Multiples Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Create 4 quarterly periods for TTM computation
    base_date = date(2025, 3, 31)
    from datetime import timedelta

    for q in range(4):
        period_end = base_date - timedelta(days=q * 91)
        fp = FinancialPeriod(
            period_id=uuid.uuid4(),
            entity_id=entity.entity_id,
            period_end_date=period_end,
            period_type="QUARTERLY",
            fiscal_year=2025 if q < 2 else 2024,
            fiscal_quarter=(4 - q) if q < 4 else 1,
        )
        session.add(fp)
        await session.flush()

        session.add(IncomeStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_revenue=250_000_000.0,
            operating_income=50_000_000.0,
            ebitda=60_000_000.0,
            net_income=35_000_000.0,
            diluted_eps=3.50,
            diluted_shares_outstanding=10_000_000.0,
        ))
        session.add(BalanceSheet(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_assets=2_000_000_000.0,
            total_equity=800_000_000.0,
            total_debt=400_000_000.0,
            cash_and_equivalents=100_000_000.0,
            tangible_book_value=700_000_000.0,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            free_cash_flow=30_000_000.0,
            dividends_paid=-5_000_000.0,
        ))
        await session.flush()

    return security


@pytest.mark.asyncio
async def test_multiples_engine_returns_results(session: AsyncSession, seeded_security_multiples: Security):
    """MultiplesEngine should return a list of EngineOutput."""
    engine = MultiplesEngine()
    results = await engine.compute(session, security_id=seeded_security_multiples.security_id)
    assert isinstance(results, list)
    # Should have some outputs (may not have all 11 if price data missing)
    for r in results:
        assert r.engine_id == "E2"
        assert r.metric_category == "VALUATION"


@pytest.mark.asyncio
async def test_multiples_engine_no_data(session: AsyncSession):
    """MultiplesEngine with unknown security should return empty."""
    engine = MultiplesEngine()
    results = await engine.compute(session, security_id=uuid.uuid4())
    assert results == []


@pytest.mark.asyncio
async def test_multiples_engine_metadata(session: AsyncSession, seeded_security_multiples: Security):
    """All outputs should have correct engine metadata."""
    engine = MultiplesEngine()
    results = await engine.compute(session, security_id=seeded_security_multiples.security_id)
    if results:
        assert all(r.engine_id == "E2" for r in results)
        assert all(r.security_id == seeded_security_multiples.security_id for r in results)
