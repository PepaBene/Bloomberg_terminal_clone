"""Tests for E2 DCF Valuation Engine (FCFF and FCFE models)."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import WACCResult
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import EODPrice, EquityDetails, Security


# ---------------------------------------------------------------------------
# Fixtures — entity with 3 annual periods, security, WACC, price
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def dcf_entity(session: AsyncSession) -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="DCF Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        gics_sector="45",
        gics_sub_industry="45103010",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


@pytest_asyncio.fixture
async def dcf_security(session: AsyncSession, dcf_entity: Entity) -> Security:
    security = Security(
        security_id=uuid.uuid4(),
        name="DCF Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=dcf_entity.entity_id,
    )
    session.add(security)
    await session.flush()

    # Equity details: 50M shares outstanding
    eq = EquityDetails(
        security_id=security.security_id,
        shares_outstanding=50_000_000.0,
    )
    session.add(eq)
    await session.flush()
    return security


@pytest_asyncio.fixture
async def dcf_periods(
    session: AsyncSession,
    dcf_entity: Entity,
) -> list[FinancialPeriod]:
    """Create 3 annual periods (2022, 2023, 2024) with IS+BS+CF."""
    periods = []
    yearly_data = [
        # (year, revenue, cogs, gross, opinc, pretax, ni, interest_exp, tax_exp, eff_tax, sga, da, ebitda, diluted_shares,
        #  total_assets, ca, cl, liab, equity, debt, ltd, cash, ar, ppe, re, wc, tbv,
        #  cfo, capex, fcf, divs_paid, cf_da)
        (2022,
         400e6, 240e6, 160e6, 60e6, 52e6, 40e6, 8e6, 12e6, 0.23, 55e6, 18e6, 78e6, 50e6,
         700e6, 200e6, 120e6, 420e6, 280e6, 180e6, 160e6, 50e6, 50e6, 180e6, 120e6, 80e6, 200e6,
         55e6, -25e6, 30e6, -10e6, 18e6),
        (2023,
         500e6, 300e6, 200e6, 80e6, 70e6, 56e6, 10e6, 14e6, 0.20, 70e6, 20e6, 100e6, 50e6,
         800e6, 250e6, 150e6, 500e6, 300e6, 200e6, 180e6, 60e6, 60e6, 200e6, 150e6, 100e6, 220e6,
         70e6, -30e6, 40e6, -12e6, 20e6),
        (2024,
         600e6, 340e6, 260e6, 110e6, 100e6, 80e6, 10e6, 20e6, 0.20, 80e6, 22e6, 132e6, 50e6,
         900e6, 300e6, 140e6, 530e6, 370e6, 180e6, 160e6, 80e6, 70e6, 220e6, 220e6, 160e6, 290e6,
         95e6, -35e6, 60e6, -15e6, 22e6),
    ]

    for (year, rev, cogs, gp, opinc, pretax, ni, int_exp, tax_exp, eff_tax,
         sga, da, ebitda_val, dil_shares,
         ta, ca, cl, liab, eq, debt, ltd, cash, ar, ppe, re, wc, tbv,
         cfo, capex, fcf, divs, cf_da) in yearly_data:

        fp = FinancialPeriod(
            period_id=uuid.uuid4(),
            entity_id=dcf_entity.entity_id,
            period_end_date=date(year, 12, 31),
            period_type="ANNUAL",
            fiscal_year=year,
            fiscal_quarter=None,
        )
        session.add(fp)
        await session.flush()

        session.add(IncomeStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_revenue=rev,
            cost_of_revenue=cogs,
            gross_profit=gp,
            operating_income=opinc,
            pretax_income=pretax,
            net_income=ni,
            interest_expense=int_exp,
            income_tax_expense=tax_exp,
            effective_tax_rate=eff_tax,
            selling_general_admin=sga,
            depreciation_amortization=da,
            ebitda=ebitda_val,
            diluted_shares_outstanding=dil_shares,
        ))
        session.add(BalanceSheet(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_assets=ta,
            total_current_assets=ca,
            total_current_liabilities=cl,
            total_liabilities=liab,
            total_equity=eq,
            total_debt=debt,
            long_term_debt=ltd,
            cash_and_equivalents=cash,
            accounts_receivable=ar,
            ppe_net=ppe,
            retained_earnings=re,
            working_capital=wc,
            tangible_book_value=tbv,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            cash_from_operations=cfo,
            capital_expenditures=capex,
            free_cash_flow=fcf,
            dividends_paid=divs,
            depreciation_amortization=cf_da,
        ))
        await session.flush()
        periods.append(fp)

    return periods


@pytest_asyncio.fixture
async def dcf_wacc(
    session: AsyncSession,
    dcf_entity: Entity,
    dcf_security: Security,
) -> WACCResult:
    wacc = WACCResult(
        entity_id=dcf_entity.entity_id,
        security_id=dcf_security.security_id,
        calculation_date=date(2025, 1, 15),
        wacc=0.10,
        cost_of_equity=0.12,
        risk_free_rate=0.04,
        equity_risk_premium=0.06,
        beta=1.1,
        cost_of_debt_pretax=0.05,
        effective_tax_rate=0.20,
        cost_of_debt_aftertax=0.04,
        debt_weight=0.30,
        equity_weight=0.70,
        market_cap=5_000_000_000.0,
        total_debt=180_000_000.0,
        data_quality="COMPLETE",
    )
    session.add(wacc)
    await session.flush()
    return wacc


@pytest_asyncio.fixture
async def dcf_price(
    session: AsyncSession,
    dcf_security: Security,
) -> EODPrice:
    price = EODPrice(
        security_id=dcf_security.security_id,
        price_date=date(2025, 3, 14),
        open=99.0,
        high=101.0,
        low=98.5,
        close=100.0,
        close_adjusted=100.0,
        volume=1_000_000,
    )
    session.add(price)
    await session.flush()
    return price


# ---------------------------------------------------------------------------
# DCF FCFF Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dcf_fcff_basic(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """FCFF DCF returns results with a numeric implied price."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    assert len(results) > 0
    by_name = {r.metric_name: r.value for r in results}
    assert "dcf_implied_price" in by_name
    assert by_name["dcf_implied_price"] is not None
    assert isinstance(by_name["dcf_implied_price"], float)


@pytest.mark.asyncio
async def test_dcf_produces_key_metrics(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """DCF engine produces all key valuation metrics."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)
    by_name = {r.metric_name: r for r in results}

    for key in ("dcf_enterprise_value", "dcf_equity_value",
                "dcf_implied_price", "dcf_upside_downside"):
        assert key in by_name, f"Missing key metric: {key}"


@pytest.mark.asyncio
async def test_dcf_method_is_fcff(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """Default DCF method should be FCFF (stored in data_quality of dcf_method)."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    by_name = {r.metric_name: r for r in results}
    method_output = by_name.get("dcf_method")
    assert method_output is not None
    assert method_output.data_quality == "FCFF"


@pytest.mark.asyncio
async def test_dcf_terminal_pct_reasonable(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """Terminal value as a percentage of EV should be < 95%."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    by_name = {r.metric_name: r.value for r in results}
    terminal_pct = by_name.get("dcf_terminal_pct_of_ev")
    assert terminal_pct is not None
    assert terminal_pct < 0.95


@pytest.mark.asyncio
async def test_dcf_positive_enterprise_value(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """Enterprise value should be positive for a healthy company."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    by_name = {r.metric_name: r.value for r in results}
    ev = by_name.get("dcf_enterprise_value")
    assert ev is not None
    assert ev > 0


@pytest.mark.asyncio
async def test_dcf_implied_vs_current(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """dcf_implied_vs_current should classify as UNDERVALUED, FAIRLY_VALUED, or OVERVALUED."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    by_name = {r.metric_name: r for r in results}
    ivc = by_name.get("dcf_implied_vs_current")
    assert ivc is not None
    assert ivc.data_quality in ("UNDERVALUED", "FAIRLY_VALUED", "OVERVALUED", "UNKNOWN")


@pytest.mark.asyncio
async def test_dcf_no_data_returns_empty(session: AsyncSession):
    """Security with no financials should produce empty results."""
    from src.engines.e2_dcf import DCFEngine

    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Empty DCF Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Empty DCF Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    engine = DCFEngine()
    results = await engine.compute(session, security_id=security.security_id)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_dcf_engine_id(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """All DCF outputs should have engine_id='E2'."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(session, security_id=dcf_security.security_id)

    assert len(results) > 0
    for r in results:
        assert r.engine_id == "E2"


@pytest.mark.asyncio
async def test_dcf_sensitivity_grid_exists(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """DCF should persist a DCFResult with a non-empty sensitivity grid."""
    from src.engines.e2_dcf import DCFEngine
    from src.models.analytics import DCFResult
    from sqlalchemy import select

    engine = DCFEngine()
    await engine.compute(session, security_id=dcf_security.security_id)
    await session.flush()

    stmt = select(DCFResult).where(
        DCFResult.security_id == dcf_security.security_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    assert row is not None
    assert row.sensitivity_grid is not None
    assert "wacc_values" in row.sensitivity_grid
    assert "growth_values" in row.sensitivity_grid
    assert "implied_prices" in row.sensitivity_grid
    assert len(row.sensitivity_grid["implied_prices"]) > 0


@pytest.mark.asyncio
async def test_dcf_fcfe_method(
    session: AsyncSession,
    dcf_security: Security,
    dcf_periods: list,
    dcf_wacc: WACCResult,
    dcf_price: EODPrice,
):
    """FCFE method should produce results with dcf_method='FCFE'."""
    from src.engines.e2_dcf import DCFEngine

    engine = DCFEngine()
    results = await engine.compute(
        session, security_id=dcf_security.security_id, method="FCFE"
    )

    assert len(results) > 0
    by_name = {r.metric_name: r for r in results}
    method_output = by_name.get("dcf_method")
    assert method_output is not None
    assert method_output.data_quality == "FCFE"

    # FCFE should also produce an implied price
    assert by_name.get("dcf_implied_price") is not None
