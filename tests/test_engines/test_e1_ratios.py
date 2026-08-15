"""Tests for E1 RatioEngine — validates both existing and newly added ratios."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.engines.base import EngineOutput, cagr, pct_change, safe_divide
from src.engines.e1_ratios import RatioEngine, _ComputeContext, _FinancialSnapshot, _PriceSnapshot


# ---------------------------------------------------------------------------
# Helpers: build lightweight mock snapshots without a real DB
# ---------------------------------------------------------------------------

def _make_income(overrides: dict | None = None) -> MagicMock:
    """Build a mock IncomeStatement with sensible defaults."""
    defaults = dict(
        total_revenue=1_000_000,
        cost_of_revenue=600_000,
        gross_profit=400_000,
        operating_income=200_000,
        ebitda=250_000,
        net_income=150_000,
        net_income_to_common=145_000,
        pretax_income=180_000,
        interest_expense=20_000,
        income_tax_expense=30_000,
        depreciation_amortization=50_000,
        research_development=80_000,
        selling_general_admin=120_000,
        stock_based_compensation=10_000,
        effective_tax_rate=0.167,
        basic_eps=3.0,
        diluted_eps=2.9,
        basic_shares_outstanding=50_000,
        diluted_shares_outstanding=51_000,
        employee_count=500,
    )
    if overrides:
        defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_balance(overrides: dict | None = None) -> MagicMock:
    defaults = dict(
        total_assets=2_000_000,
        total_equity=800_000,
        total_common_equity=780_000,
        total_debt=500_000,
        total_current_assets=600_000,
        total_current_liabilities=400_000,
        total_liabilities=1_200_000,
        net_debt=200_000,
        cash_and_equivalents=300_000,
        cash_and_short_term=320_000,
        inventory=100_000,
        accounts_receivable=150_000,
        accounts_payable=80_000,
        ppe_net=500_000,
        working_capital=200_000,
        tangible_book_value=600_000,
        goodwill=100_000,
        intangible_assets=80_000,
        long_term_debt=400_000,
        short_term_debt=100_000,
        employee_count=500,
    )
    if overrides:
        defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_cashflow(overrides: dict | None = None) -> MagicMock:
    defaults = dict(
        cash_from_operations=200_000,
        free_cash_flow=120_000,
        capital_expenditures=-80_000,
        dividends_paid=-30_000,
        stock_repurchased=-50_000,
        operating_lease_payments=15_000,
    )
    if overrides:
        defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_snapshot(
    end_date: date = date(2024, 12, 31),
    fiscal_year: int = 2024,
    inc_overrides: dict | None = None,
    bs_overrides: dict | None = None,
    cf_overrides: dict | None = None,
) -> _FinancialSnapshot:
    """Create a _FinancialSnapshot backed by mocks."""
    period = MagicMock()
    period.period_end_date = end_date
    period.period_type = "ANNUAL"
    period.fiscal_year = fiscal_year
    period.fiscal_quarter = None
    period.income_statement = _make_income(inc_overrides)
    period.balance_sheet = _make_balance(bs_overrides)
    period.cash_flow = _make_cashflow(cf_overrides)
    return _FinancialSnapshot(period)


def _make_context(
    snapshots: list[_FinancialSnapshot] | None = None,
    market_cap: float = 5_000_000,
    close: float = 100.0,
    fwd_eps: float | None = 3.2,
) -> _ComputeContext:
    """Build a _ComputeContext for unit testing ratio functions."""
    if snapshots is None:
        latest = _make_snapshot()
        prior = _make_snapshot(date(2023, 12, 31), 2023)
        prior_3y = _make_snapshot(date(2021, 12, 31), 2021)
        prior_5y = _make_snapshot(date(2019, 12, 31), 2019)
        snapshots = [latest, prior, prior_3y, prior_5y]
    price = _PriceSnapshot(
        close=close,
        market_cap=market_cap,
        shares_diluted=51_000,
        shares_basic=50_000,
        price_date=date(2025, 1, 2),
    )
    return _ComputeContext(
        security_id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        latest=snapshots[0],
        snapshots=snapshots,
        price=price,
        fwd_eps=fwd_eps,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBaseHelpers:
    """Ensure helper functions work correctly."""

    def test_safe_divide_normal(self):
        assert safe_divide(10, 5) == 2.0

    def test_safe_divide_zero_denominator(self):
        assert safe_divide(10, 0) is None

    def test_safe_divide_none(self):
        assert safe_divide(None, 5) is None
        assert safe_divide(10, None) is None

    def test_pct_change_normal(self):
        assert pct_change(110, 100) == pytest.approx(0.1)

    def test_pct_change_zero_prior(self):
        assert pct_change(100, 0) is None

    def test_cagr_normal(self):
        result = cagr(200, 100, 5)
        assert result is not None
        assert result == pytest.approx((200 / 100) ** 0.2 - 1)

    def test_cagr_negative_values(self):
        assert cagr(-100, 50, 3) is None


class TestProfitabilityRatios:
    """Test profitability category outputs including new ratios."""

    def test_gross_margin(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._profitability(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "gross_margin" in names
        gm = names["gross_margin"]
        assert gm.value == pytest.approx(400_000 / 1_000_000)

    def test_earnings_yield(self):
        engine = RatioEngine()
        ctx = _make_context(market_cap=5_000_000)
        outputs = engine._profitability(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "earnings_yield" in names
        ey = names["earnings_yield"]
        assert ey.value == pytest.approx(150_000 / 5_000_000)

    def test_ebitda_to_interest(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._profitability(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "ebitda_to_interest" in names
        val = names["ebitda_to_interest"]
        assert val.value == pytest.approx(250_000 / 20_000)


class TestLeverageRatios:
    """Test leverage category including new ratios."""

    def test_debt_to_equity(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._leverage(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "debt_to_equity" in names
        assert names["debt_to_equity"].value == pytest.approx(500_000 / 800_000)

    def test_fixed_charge_coverage(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._leverage(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "fixed_charge_coverage" in names
        fcc = names["fixed_charge_coverage"]
        # (250000 + 15000) / (20000 + 15000) = 265000 / 35000
        assert fcc.value == pytest.approx(265_000 / 35_000)

    def test_debt_growth_yoy(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._leverage(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "debt_growth_yoy" in names
        # Both periods have same total_debt=500000, so pct_change=0, *100=0
        assert names["debt_growth_yoy"].value == pytest.approx(0.0)

    def test_debt_growth_yoy_stores_fraction_not_percent(self):
        """Regression test: debt_growth_yoy previously stored
        pct_change() * 100, double-scaling relative to every sibling
        growth metric (fcf_yoy, book_value_yoy, dividend_yoy, ...), which
        all store the raw pct_change()/cagr() fraction directly."""
        engine = RatioEngine()
        latest = _make_snapshot(bs_overrides={"total_debt": 550_000})
        prior = _make_snapshot(date(2023, 12, 31), 2023, bs_overrides={"total_debt": 500_000})
        prior_3y = _make_snapshot(date(2021, 12, 31), 2021)
        prior_5y = _make_snapshot(date(2019, 12, 31), 2019)
        ctx = _make_context(snapshots=[latest, prior, prior_3y, prior_5y])
        outputs = engine._leverage(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "debt_growth_yoy" in names
        # (550000 - 500000) / 500000 = 0.10 (a fraction, NOT 10.0)
        assert names["debt_growth_yoy"].value == pytest.approx(0.10)


class TestEfficiencyRatios:
    """Test efficiency category including new ratio."""

    def test_asset_turnover(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._efficiency(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "asset_turnover" in names
        assert names["asset_turnover"].value == pytest.approx(1_000_000 / 2_000_000)

    def test_revenue_to_fixed_assets(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._efficiency(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "revenue_to_fixed_assets" in names
        assert names["revenue_to_fixed_assets"].value == pytest.approx(1_000_000 / 500_000)


class TestGrowthRatios:
    """Test growth category including new ratios."""

    def test_revenue_yoy(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._growth(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "revenue_yoy" in names

    def test_tangible_bvps_yoy(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._growth(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "tangible_bvps_yoy" in names
        # Both snapshots have same tangible_book_value=600000, so 0%
        assert names["tangible_bvps_yoy"].value == pytest.approx(0.0)

    def test_tangible_bvps_yoy_stores_fraction_not_percent(self):
        """Regression test: tangible_bvps_yoy previously stored
        pct_change() * 100, the same double-scaling bug as
        debt_growth_yoy -- store the raw fraction."""
        engine = RatioEngine()
        latest = _make_snapshot(bs_overrides={"tangible_book_value": 660_000})
        prior = _make_snapshot(date(2023, 12, 31), 2023, bs_overrides={"tangible_book_value": 600_000})
        prior_3y = _make_snapshot(date(2021, 12, 31), 2021)
        prior_5y = _make_snapshot(date(2019, 12, 31), 2019)
        ctx = _make_context(snapshots=[latest, prior, prior_3y, prior_5y])
        outputs = engine._growth(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "tangible_bvps_yoy" in names
        # (660000 - 600000) / 600000 = 0.10 (a fraction, NOT 10.0)
        assert names["tangible_bvps_yoy"].value == pytest.approx(0.10)

    def test_debt_growth_3y_cagr(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._growth(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "debt_growth_3y_cagr" in names
        # Same total_debt across periods: CAGR(500000, 500000, 3) = 0
        val = names["debt_growth_3y_cagr"].value
        assert val == pytest.approx(0.0)

    def test_operating_income_5y_cagr(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._growth(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "operating_income_5y_cagr" in names


class TestPerShareRatios:
    """Test per-share category including new ratios."""

    def test_eps_basic(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._per_share(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "eps_basic" in names
        assert names["eps_basic"].value == pytest.approx(3.0)

    # Pillar 2 audit Bug 26: net_income_per_employee and
    # revenue_per_employee were removed because no model populates the
    # ``employee_count`` field. Both metrics silently emitted None for
    # every security; the fix dropped them rather than adding an
    # un-populated column. The tests below assert their absence so a
    # future regression that re-adds them without the data will fail.
    def test_per_employee_metrics_removed(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._per_share(ctx)
        names = {o.metric_name for o in outputs}
        assert "net_income_per_employee" not in names
        assert "revenue_per_employee" not in names


class TestCashFlowQualityRatios:
    """Test cash flow quality category including new ratios."""

    def test_ocf_to_net_income(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._cash_flow_quality(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "ocf_to_net_income" in names
        assert names["ocf_to_net_income"].value == pytest.approx(200_000 / 150_000)

    def test_operating_cf_to_debt(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._cash_flow_quality(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "operating_cf_to_debt" in names
        assert names["operating_cf_to_debt"].value == pytest.approx(200_000 / 500_000)

    def test_fcf_to_debt(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._cash_flow_quality(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "fcf_to_debt" in names
        assert names["fcf_to_debt"].value == pytest.approx(120_000 / 500_000)


class TestDividendRatios:
    """Test dividend category including new ratios."""

    def test_dividend_yield_trailing(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._dividend(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "dividend_yield_trailing" in names

    def test_consecutive_dividend_years(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._dividend(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "consecutive_dividend_years" in names
        # All 4 snapshots have dividends_paid=-30000 (non-zero), so consec=4
        assert names["consecutive_dividend_years"].value == 4.0

    def test_consecutive_dividend_years_with_gap(self):
        """A zero-dividend period breaks the streak."""
        engine = RatioEngine()
        latest = _make_snapshot()
        prior = _make_snapshot(date(2023, 12, 31), 2023, cf_overrides={"dividends_paid": 0})
        prior_3y = _make_snapshot(date(2021, 12, 31), 2021)
        ctx = _make_context(snapshots=[latest, prior, prior_3y])
        outputs = engine._dividend(ctx)
        names = {o.metric_name: o for o in outputs}
        # Only the latest has dividends, prior=0 breaks streak
        assert names["consecutive_dividend_years"].value == 1.0

    def test_dividend_growth_10y_cagr(self):
        engine = RatioEngine()
        ctx = _make_context()
        outputs = engine._dividend(ctx)
        names = {o.metric_name: o for o in outputs}
        assert "dividend_growth_10y_cagr" in names
        # No 10y prior in our fixture (only 5y back), so value should be None
        assert names["dividend_growth_10y_cagr"].value is None


class TestEngineOutputStructure:
    """Validate that outputs conform to the EngineOutput contract."""

    def test_all_outputs_have_required_fields(self):
        engine = RatioEngine()
        ctx = _make_context()
        for method in [
            engine._profitability,
            engine._leverage,
            engine._efficiency,
            engine._growth,
            engine._per_share,
            engine._cash_flow_quality,
            engine._capital_allocation,
            engine._dividend,
        ]:
            outputs = method(ctx)
            for o in outputs:
                assert isinstance(o, EngineOutput)
                assert o.engine_id == "E1"
                assert o.metric_name
                assert o.metric_category
                assert o.unit
                assert o.security_id == ctx.security_id

    def test_total_ratio_count_exceeds_100(self):
        """After additions, E1 should produce at least 100 distinct ratios."""
        engine = RatioEngine()
        ctx = _make_context()
        all_outputs = []
        for method in [
            engine._profitability,
            engine._leverage,
            engine._efficiency,
            engine._growth,
            engine._per_share,
            engine._cash_flow_quality,
            engine._capital_allocation,
            engine._dividend,
        ]:
            all_outputs.extend(method(ctx))
        unique_names = {o.metric_name for o in all_outputs}
        assert len(unique_names) >= 100, f"Only {len(unique_names)} unique ratios found"
