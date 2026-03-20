"""Tests for E8 Scenario & Sensitivity Engine."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e8_scenario import ScenarioEngine
from src.models.analytics import WACCResult
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.scenario import ScenarioResult
from src.models.security import EODPrice, EquityDetails, Security


# ---------------------------------------------------------------------------
# Fixtures — reuse same seeding pattern as E2 DCF tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def scn_entity(session: AsyncSession) -> Entity:
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Scenario Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


@pytest_asyncio.fixture
async def scn_security(session: AsyncSession, scn_entity: Entity) -> Security:
    security = Security(
        security_id=uuid.uuid4(),
        name="Scenario Test Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=scn_entity.entity_id,
    )
    session.add(security)
    await session.flush()

    eq = EquityDetails(
        security_id=security.security_id,
        shares_outstanding=50_000_000.0,
    )
    session.add(eq)
    await session.flush()
    return security


@pytest_asyncio.fixture
async def scn_periods(session: AsyncSession, scn_entity: Entity) -> list[FinancialPeriod]:
    """3 annual periods (2022-2024) with IS+BS+CF."""
    periods = []
    yearly_data = [
        (2022, 400e6, 240e6, 160e6, 60e6, 52e6, 40e6, 8e6, 12e6, 0.23, 55e6, 18e6,
         700e6, 200e6, 120e6, 420e6, 280e6, 180e6, 160e6, 50e6, 80e6, 200e6,
         55e6, -25e6, 30e6, 18e6),
        (2023, 500e6, 300e6, 200e6, 80e6, 70e6, 56e6, 10e6, 14e6, 0.20, 70e6, 20e6,
         800e6, 250e6, 150e6, 500e6, 300e6, 200e6, 180e6, 60e6, 100e6, 220e6,
         70e6, -30e6, 40e6, 20e6),
        (2024, 600e6, 340e6, 260e6, 110e6, 100e6, 80e6, 10e6, 20e6, 0.20, 80e6, 22e6,
         900e6, 300e6, 140e6, 530e6, 370e6, 180e6, 160e6, 80e6, 160e6, 290e6,
         95e6, -35e6, 60e6, 22e6),
    ]

    for (year, rev, cogs, gp, opinc, pretax, ni, int_exp, tax_exp, eff_tax, sga, da,
         ta, ca, cl, liab, eq, debt, ltd, cash, wc, tbv,
         cfo, capex, fcf, cf_da) in yearly_data:

        fp = FinancialPeriod(
            period_id=uuid.uuid4(),
            entity_id=scn_entity.entity_id,
            period_end_date=date(year, 12, 31),
            period_type="ANNUAL",
            fiscal_year=year,
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
            working_capital=wc,
            tangible_book_value=tbv,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            cash_from_operations=cfo,
            capital_expenditures=capex,
            free_cash_flow=fcf,
            depreciation_amortization=cf_da,
        ))
        await session.flush()
        periods.append(fp)

    return periods


@pytest_asyncio.fixture
async def scn_wacc(session: AsyncSession, scn_entity: Entity, scn_security: Security) -> WACCResult:
    wacc = WACCResult(
        entity_id=scn_entity.entity_id,
        security_id=scn_security.security_id,
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
async def scn_price(session: AsyncSession, scn_security: Security) -> EODPrice:
    price = EODPrice(
        security_id=scn_security.security_id,
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


@pytest_asyncio.fixture
async def scenario_engine() -> ScenarioEngine:
    return ScenarioEngine()


# Convenience fixture that seeds everything
@pytest_asyncio.fixture
async def seeded(scn_entity, scn_security, scn_periods, scn_wacc, scn_price):
    return scn_entity, scn_security


# ---------------------------------------------------------------------------
# 2D Sensitivity Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitivity_2d_grid_shape(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
    )
    assert result is not None
    assert len(result["row_values"]) == 5
    assert len(result["col_values"]) == 5
    assert len(result["grid"]) == 5
    assert all(len(row) == 5 for row in result["grid"])


@pytest.mark.asyncio
async def test_sensitivity_2d_auto_ranges(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
    )
    assert result is not None
    # Default is 7 steps
    assert len(result["row_values"]) == 7
    assert len(result["col_values"]) == 7


@pytest.mark.asyncio
async def test_sensitivity_2d_monotonicity_discount_rate(session: AsyncSession, seeded, scenario_engine):
    """Higher WACC → lower implied price (holding terminal growth constant)."""
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
        persist=False,
    )
    assert result is not None
    grid = result["grid"]
    col_mid = len(result["col_values"]) // 2
    # Check column mid: as row index increases (higher discount_rate), price should decrease
    col_prices = [grid[r][col_mid] for r in range(len(grid)) if grid[r][col_mid] is not None]
    for i in range(len(col_prices) - 1):
        assert col_prices[i] >= col_prices[i + 1], \
            f"Price should decrease as discount_rate increases: {col_prices}"


@pytest.mark.asyncio
async def test_sensitivity_2d_monotonicity_growth(session: AsyncSession, seeded, scenario_engine):
    """Higher terminal growth → higher implied price (holding WACC constant)."""
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
        persist=False,
    )
    assert result is not None
    grid = result["grid"]
    row_mid = len(result["row_values"]) // 2
    row_prices = [grid[row_mid][c] for c in range(len(grid[row_mid])) if grid[row_mid][c] is not None]
    for i in range(len(row_prices) - 1):
        assert row_prices[i] <= row_prices[i + 1], \
            f"Price should increase as terminal_growth increases: {row_prices}"


@pytest.mark.asyncio
async def test_sensitivity_2d_persistence(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
    )
    assert result is not None

    rows = (await session.execute(
        select(ScenarioResult).where(
            ScenarioResult.security_id == security.security_id,
            ScenarioResult.scenario_type == "SENSITIVITY_2D",
        )
    )).scalars().all()
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_sensitivity_2d_base_case_present(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
        persist=False,
    )
    assert result is not None
    assert result["base_case_value"] is not None
    assert isinstance(result["base_case_value"], float)


@pytest.mark.asyncio
async def test_sensitivity_2d_fcfe_method(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_2d(
        session, security.security_id,
        row_variable="ebit_margin",
        col_variable="revenue_growth",
        steps=5,
        method="FCFE",
        persist=False,
    )
    assert result is not None
    assert result["base_case_value"] is not None


# ---------------------------------------------------------------------------
# 3D Sensitivity Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitivity_3d_table_count(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_3d(
        session, security.security_id,
        fixed_variable="tax_rate",
        fixed_values=[0.15, 0.21, 0.28],
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=5,
    )
    assert result is not None
    assert len(result["tables"]) == 3


@pytest.mark.asyncio
async def test_sensitivity_3d_different_base_cases(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_sensitivity_3d(
        session, security.security_id,
        fixed_variable="tax_rate",
        fixed_values=[0.10, 0.30],
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=3,
        persist=False,
    )
    assert result is not None
    t1 = result["tables"][0]["base_case_value"]
    t2 = result["tables"][1]["base_case_value"]
    # Lower tax → higher price
    assert t1 is not None and t2 is not None
    assert t1 > t2, "Lower tax rate should yield higher base case price"


@pytest.mark.asyncio
async def test_sensitivity_3d_persistence(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    await scenario_engine.run_sensitivity_3d(
        session, security.security_id,
        fixed_variable="tax_rate",
        fixed_values=[0.15, 0.25],
        row_variable="discount_rate",
        col_variable="terminal_growth",
        steps=3,
    )
    rows = (await session.execute(
        select(ScenarioResult).where(
            ScenarioResult.scenario_type == "SENSITIVITY_3D",
        )
    )).scalars().all()
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Tornado Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tornado_sorted_descending(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_tornado(session, security.security_id, persist=False)
    assert result is not None
    bars = result["bars"]
    assert len(bars) > 0
    for i in range(len(bars) - 1):
        assert bars[i]["impact_range"] >= bars[i + 1]["impact_range"]


@pytest.mark.asyncio
async def test_tornado_custom_variables(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_tornado(
        session, security.security_id,
        variables=["discount_rate", "ebit_margin"],
        persist=False,
    )
    assert result is not None
    assert len(result["bars"]) == 2
    var_names = {b["variable"] for b in result["bars"]}
    assert var_names == {"discount_rate", "ebit_margin"}


@pytest.mark.asyncio
async def test_tornado_swing_affects_range(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    r1 = await scenario_engine.run_tornado(
        session, security.security_id,
        variables=["discount_rate"],
        swing_pct=0.10,
        persist=False,
    )
    r2 = await scenario_engine.run_tornado(
        session, security.security_id,
        variables=["discount_rate"],
        swing_pct=0.40,
        persist=False,
    )
    assert r1 is not None and r2 is not None
    # Larger swing → larger impact range
    assert r2["bars"][0]["impact_range"] > r1["bars"][0]["impact_range"]


@pytest.mark.asyncio
async def test_tornado_discount_rate_significant(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_tornado(session, security.security_id, persist=False)
    assert result is not None
    # discount_rate should be among the top 3 most impactful variables
    top3 = [b["variable"] for b in result["bars"][:3]]
    assert "discount_rate" in top3


@pytest.mark.asyncio
async def test_tornado_persistence(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    await scenario_engine.run_tornado(session, security.security_id)
    rows = (await session.execute(
        select(ScenarioResult).where(
            ScenarioResult.scenario_type == "TORNADO",
        )
    )).scalars().all()
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Shock Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shock_single_variable(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={"discount_rate": 0.02},
        persist=False,
    )
    assert result is not None
    assert result["base_case_value"] is not None
    assert result["shocked_value"] is not None
    # Higher discount rate → lower price
    assert result["shocked_value"] < result["base_case_value"]


@pytest.mark.asyncio
async def test_shock_multi_variable(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={"discount_rate": 0.03, "revenue_growth": -0.05, "ebit_margin": -0.03},
        persist=False,
    )
    assert result is not None
    assert result["shocked_value"] < result["base_case_value"]
    assert len(result["individual_impacts"]) == 3


@pytest.mark.asyncio
async def test_shock_prebuilt_scenario(session: AsyncSession, seeded, scenario_engine):
    """Run a prebuilt scenario through the shock engine."""
    from src.engines.e8_prebuilt_scenarios import PREBUILT_SCENARIOS

    _, security = seeded
    stagflation = PREBUILT_SCENARIOS["STAGFLATION"]
    result = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector=stagflation["shocks"],
        name="STAGFLATION",
        persist=False,
    )
    assert result is not None
    assert result["shocked_value"] < result["base_case_value"]


@pytest.mark.asyncio
async def test_shock_zero_delta_no_change(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    result = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={"discount_rate": 0.0},
        persist=False,
    )
    assert result is not None
    assert result["base_case_value"] == pytest.approx(result["shocked_value"], rel=1e-4)


@pytest.mark.asyncio
async def test_shock_persistence(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={"discount_rate": 0.02},
    )
    rows = (await session.execute(
        select(ScenarioResult).where(
            ScenarioResult.scenario_type == "SHOCK",
        )
    )).scalars().all()
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Breakeven Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breakeven_converges(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    # First get base case to set a reasonable target
    base = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={},
        persist=False,
    )
    assert base is not None
    target = base["base_case_value"] * 0.90  # 10% lower

    result = await scenario_engine.run_breakeven(
        session, security.security_id,
        variable="discount_rate",
        target_price=target,
        search_min=0.06,
        search_max=0.20,
        persist=False,
    )
    assert result is not None
    assert result["converged"] is True
    assert result["breakeven_value"] is not None


@pytest.mark.asyncio
async def test_breakeven_within_tolerance(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    base = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={},
        persist=False,
    )
    assert base is not None
    target = base["base_case_value"] * 0.95

    result = await scenario_engine.run_breakeven(
        session, security.security_id,
        variable="terminal_growth",
        target_price=target,
        persist=False,
    )
    assert result is not None
    if result["converged"]:
        # Verify the breakeven value actually produces close to target
        ctx = await scenario_engine._load_dcf_context(session, security.security_id)
        actual = scenario_engine._quick_dcf(
            ctx,
            scenario_engine._make_override("terminal_growth", result["breakeven_value"], ctx),
        )
        assert actual is not None
        assert abs(actual - target) <= 1.0  # within $1


@pytest.mark.asyncio
async def test_breakeven_no_solution(session: AsyncSession, seeded, scenario_engine):
    """Unreachable target price should not converge."""
    _, security = seeded
    result = await scenario_engine.run_breakeven(
        session, security.security_id,
        variable="discount_rate",
        target_price=999_999.0,  # impossibly high
        persist=False,
    )
    assert result is not None
    assert result["converged"] is False


@pytest.mark.asyncio
async def test_breakeven_different_variables(session: AsyncSession, seeded, scenario_engine):
    _, security = seeded
    base = await scenario_engine.run_shock(
        session, security.security_id,
        shock_vector={},
        persist=False,
    )
    assert base is not None
    target = base["base_case_value"] * 1.05

    for var in ("terminal_growth", "ebit_margin"):
        result = await scenario_engine.run_breakeven(
            session, security.security_id,
            variable=var,
            target_price=target,
            persist=False,
        )
        assert result is not None
        # At least one should converge
        if result["converged"]:
            assert result["breakeven_value"] is not None


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_security(session: AsyncSession, scenario_engine):
    fake_id = uuid.uuid4()
    result = await scenario_engine.run_sensitivity_2d(
        session, fake_id,
        row_variable="discount_rate",
        col_variable="terminal_growth",
    )
    assert result is None


@pytest.mark.asyncio
async def test_insufficient_data(session: AsyncSession, scenario_engine):
    """Security exists but has no financials."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Empty Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Empty Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    result = await scenario_engine.run_tornado(session, security.security_id)
    assert result is None
