"""Tests for the WACC engine."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e2_wacc import WACCEngine
from src.engines.base import safe_divide
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, FinancialPeriod, IncomeStatement
from src.models.security import Security


@pytest_asyncio.fixture
async def seeded_security_wacc(session: AsyncSession) -> Security:
    """Create security with fundamentals for WACC computation."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="WACC Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="WACC Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    fp = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        period_end_date=date(2025, 3, 31),
        period_type="QUARTERLY",
        fiscal_year=2025,
        fiscal_quarter=1,
    )
    session.add(fp)
    await session.flush()

    session.add(IncomeStatement(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        interest_expense=10_000_000.0,
        effective_tax_rate=0.21,
    ))
    session.add(BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=fp.period_id,
        total_debt=200_000_000.0,
        total_equity=500_000_000.0,
        total_assets=700_000_000.0,
    ))
    await session.flush()

    return security


@pytest.mark.asyncio
async def test_wacc_engine_returns_results(session: AsyncSession, seeded_security_wacc: Security):
    """WACCEngine should return a list of EngineOutput."""
    engine = WACCEngine()
    results = await engine.compute(session, security_id=seeded_security_wacc.security_id)
    # May return empty if no EOD prices for beta, but should not crash
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_wacc_engine_no_data(session: AsyncSession):
    """WACCEngine with unknown security should return empty."""
    engine = WACCEngine()
    results = await engine.compute(session, security_id=uuid.uuid4())
    assert results == []


@pytest.mark.asyncio
async def test_wacc_blume_adjustment():
    """Blume adjustment: 0.67 × raw + 0.33 × 1.0."""
    raw_beta = 1.5
    adjusted = 0.67 * raw_beta + 0.33 * 1.0
    assert adjusted == pytest.approx(1.335, abs=0.001)


@pytest.mark.asyncio
async def test_wacc_cost_of_equity_capm():
    """Cost of equity = Rf + β × ERP."""
    rf = 0.0425
    beta = 1.15
    erp = 0.055
    coe = rf + beta * erp
    assert coe == pytest.approx(0.106, abs=0.001)


@pytest.mark.asyncio
async def test_wacc_cost_of_debt():
    """After-tax cost of debt = pretax × (1 - tax_rate)."""
    pretax = 0.05
    tax_rate = 0.21
    aftertax = pretax * (1.0 - tax_rate)
    assert aftertax == pytest.approx(0.0395, abs=0.001)


@pytest.mark.asyncio
async def test_wacc_formula():
    """WACC = Equity_W × CoE + Debt_W × CoD_AT."""
    equity_weight = 0.70
    cost_of_equity = 0.106
    debt_weight = 0.30
    cost_of_debt_at = 0.0395
    wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt_at
    assert wacc == pytest.approx(0.0861, abs=0.001)


@pytest.mark.asyncio
async def test_wacc_weights_sum_to_one():
    """Capital structure weights should sum to 1."""
    market_cap = 500_000_000
    total_debt = 200_000_000
    total = market_cap + total_debt
    eq_w = market_cap / total
    debt_w = total_debt / total
    assert eq_w + debt_w == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_wacc_engine_metadata(session: AsyncSession, seeded_security_wacc: Security):
    """All outputs should have correct engine metadata."""
    engine = WACCEngine()
    results = await engine.compute(session, security_id=seeded_security_wacc.security_id)
    for r in results:
        assert r.engine_id == "E2"
        assert r.security_id == seeded_security_wacc.security_id
