"""Tests for the TTM (Trailing Twelve Months) engine."""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e1_ttm import TTMEngine, TTM_FLOW_FIELDS, TTM_STOCK_FIELDS
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_security(session: AsyncSession) -> Security:
    """Create a security with 4 quarters of fundamentals."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Create 4 quarterly periods with IS, BS, CF
    base_date = date(2025, 3, 31)
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
            total_revenue=100_000_000.0,  # 100M per quarter
            cost_of_revenue=60_000_000.0,
            gross_profit=40_000_000.0,
            operating_income=25_000_000.0,
            ebitda=30_000_000.0,
            net_income=18_000_000.0,
            net_income_to_common=18_000_000.0,
            interest_expense=2_000_000.0,
            income_tax_expense=5_000_000.0,
            pretax_income=23_000_000.0,
            basic_eps=1.80,
            diluted_eps=1.75,
            basic_shares_outstanding=10_000_000.0,
            diluted_shares_outstanding=10_285_714.0,
        ))
        session.add(BalanceSheet(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_assets=500_000_000.0,
            total_equity=200_000_000.0,
            total_common_equity=200_000_000.0,
            total_liabilities=300_000_000.0,
            total_current_assets=120_000_000.0,
            total_current_liabilities=80_000_000.0,
            total_debt=150_000_000.0,
            net_debt=100_000_000.0,
            cash_and_equivalents=50_000_000.0,
            accounts_receivable=30_000_000.0,
            inventory=20_000_000.0,
            accounts_payable=25_000_000.0,
            working_capital=40_000_000.0,
            tangible_book_value=180_000_000.0,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            cash_from_operations=28_000_000.0,
            capital_expenditures=-5_000_000.0,
            free_cash_flow=23_000_000.0,
            dividends_paid=-3_000_000.0,
        ))
        await session.flush()

    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ttm_sum_4_quarters(session: AsyncSession, seeded_security: Security):
    """Flow metrics should sum the 4 quarterly values."""
    engine = TTMEngine()
    results = await engine.compute(session, security_id=seeded_security.security_id)
    assert len(results) > 0

    revenue = next((r for r in results if r.metric_name in ("total_revenue", "ttm_total_revenue")), None)
    assert revenue is not None
    # 100M × 4 = 400M
    assert revenue.value == pytest.approx(400_000_000.0, rel=0.01)


@pytest.mark.asyncio
async def test_ttm_balance_sheet_uses_latest(session: AsyncSession, seeded_security: Security):
    """Stock (BS) metrics should use the latest quarter, not sum."""
    engine = TTMEngine()
    results = await engine.compute(session, security_id=seeded_security.security_id)

    total_assets = next((r for r in results if r.metric_name in ("total_assets", "ttm_total_assets")), None)
    assert total_assets is not None
    # Should be 500M (latest), not 2000M (sum)
    assert total_assets.value == pytest.approx(500_000_000.0, rel=0.01)


@pytest.mark.asyncio
async def test_ttm_returns_engine_output_list(session: AsyncSession, seeded_security: Security):
    """compute() should return list of EngineOutput."""
    engine = TTMEngine()
    results = await engine.compute(session, security_id=seeded_security.security_id)
    assert isinstance(results, list)
    for r in results:
        assert r.engine_id == "E1"
        assert r.security_id == seeded_security.security_id


@pytest.mark.asyncio
async def test_ttm_includes_key_metrics(session: AsyncSession, seeded_security: Security):
    """TTM should output at least 20 metrics."""
    engine = TTMEngine()
    results = await engine.compute(session, security_id=seeded_security.security_id)
    metric_names = {r.metric_name for r in results}
    assert len(metric_names) >= 20
    # Check key metrics present (may be prefixed with ttm_)
    has_revenue = "total_revenue" in metric_names or "ttm_total_revenue" in metric_names
    has_ni = "net_income" in metric_names or "ttm_net_income" in metric_names
    has_fcf = "free_cash_flow" in metric_names or "ttm_free_cash_flow" in metric_names
    has_assets = "total_assets" in metric_names or "ttm_total_assets" in metric_names
    has_equity = "total_equity" in metric_names or "ttm_total_equity" in metric_names
    assert has_revenue
    assert has_ni
    assert has_fcf
    assert has_assets
    assert has_equity


@pytest.mark.asyncio
async def test_ttm_handles_no_fundamentals(session: AsyncSession):
    """TTM with no data should return empty list."""
    engine = TTMEngine()
    # Use a random UUID that doesn't exist
    results = await engine.compute(session, security_id=uuid.uuid4())
    assert results == []


@pytest.mark.asyncio
async def test_ttm_field_registries():
    """TTM_FLOW_FIELDS and TTM_STOCK_FIELDS should be non-empty dicts."""
    assert len(TTM_FLOW_FIELDS) >= 15
    assert len(TTM_STOCK_FIELDS) >= 10
    # Every entry should be a (class, str) tuple
    for name, (cls, field) in TTM_FLOW_FIELDS.items():
        assert isinstance(name, str)
        assert isinstance(field, str)
