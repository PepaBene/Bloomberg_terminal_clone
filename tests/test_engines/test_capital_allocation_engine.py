"""Tests for Pillar 3 Phase 2 — Part 7b: Capital Allocation Analysis Engine."""

from src.engines.capital_allocation_engine import (
    BuybackEffectiveness,
    CapExClassification,
    CapitalAllocationResult,
    DividendSustainability,
    FCFConversion,
    MADiscipline,
    WorkingCapitalDiscipline,
    analyze_capital_allocation,
    assess_buyback_effectiveness,
    assess_dividend_sustainability,
    assess_ma_discipline,
    classify_capex,
    compute_capital_allocation_score,
    compute_fcf_conversion,
    compute_working_capital_discipline,
)


# ── FCF Conversion Tests ─────────────────────────────────────────────────


class TestFCFConversion:
    """Tests for compute_fcf_conversion()."""

    def test_good_conversion_above_80(self):
        """Healthy FCF conversion: FCF/EBITDA > 80%."""
        result = compute_fcf_conversion(
            ebitda=5_000.0,
            fcf=4_500.0,
            capex=-800.0,
            working_capital_change=-200.0,
        )
        assert isinstance(result, FCFConversion)
        assert result.ebitda_to_fcf_ratio == 0.9
        assert result.is_red_flag is False
        assert "capex_pct_of_ebitda" in result.gap_decomposition
        assert "wc_change_pct_of_ebitda" in result.gap_decomposition

    def test_red_flag_below_50(self):
        """Poor FCF conversion: FCF/EBITDA < 50% triggers red flag."""
        result = compute_fcf_conversion(ebitda=10_000.0, fcf=3_500.0)
        assert result.ebitda_to_fcf_ratio == 0.35
        assert result.is_red_flag is True

    def test_missing_data(self):
        """None EBITDA or FCF returns empty result."""
        result = compute_fcf_conversion(ebitda=None, fcf=1_000.0)
        assert result.ebitda_to_fcf_ratio is None
        assert result.is_red_flag is False

        result2 = compute_fcf_conversion(ebitda=5_000.0, fcf=None)
        assert result2.ebitda_to_fcf_ratio is None


# ── CapEx Classification Tests ───────────────────────────────────────────


class TestClassifyCapex:
    """Tests for classify_capex()."""

    def test_maintenance_plus_growth_split(self):
        """CapEx exceeds depreciation -> growth component exists."""
        result = classify_capex(
            total_capex=-3_000.0,
            depreciation=-1_800.0,
            revenue=50_000.0,
        )
        assert isinstance(result, CapExClassification)
        assert result.total_capex == 3_000.0
        assert result.maintenance_capex == 1_800.0
        assert result.growth_capex == 1_200.0
        assert result.growth_capex_revenue_pct == 0.024  # 1200/50000
        assert result.maintenance_capex_revenue_pct == 0.036  # 1800/50000

    def test_zero_depreciation(self):
        """Zero depreciation means all CapEx is growth."""
        result = classify_capex(total_capex=-500.0, depreciation=0.0, revenue=10_000.0)
        assert result.maintenance_capex == 0.0
        assert result.growth_capex == 500.0

    def test_missing_capex(self):
        """None CapEx returns empty classification."""
        result = classify_capex(total_capex=None, depreciation=-200.0)
        assert result.total_capex is None
        assert result.maintenance_capex is None


# ── Working Capital Discipline Tests ─────────────────────────────────────


class TestWorkingCapitalDiscipline:
    """Tests for compute_working_capital_discipline()."""

    def test_computed_ccc_dio_dso_dpo(self):
        """Full working capital metrics from realistic balance sheet data."""
        result = compute_working_capital_discipline(
            receivables=8_000.0,
            inventory=5_000.0,
            payables=6_000.0,
            revenue=100_000.0,
            cogs=65_000.0,
        )
        assert isinstance(result, WorkingCapitalDiscipline)
        # DSO = 8000/100000 * 365 = 29.2
        assert result.dso is not None
        assert 29.0 <= result.dso <= 30.0
        # DIO = 5000/65000 * 365 ≈ 28.1
        assert result.dio is not None
        assert 28.0 <= result.dio <= 29.0
        # DPO = 6000/65000 * 365 ≈ 33.7
        assert result.dpo is not None
        assert 33.0 <= result.dpo <= 34.0
        # CCC = DSO + DIO - DPO ≈ 29.2 + 28.1 - 33.7 ≈ 23.6
        assert result.ccc is not None
        assert 23.0 <= result.ccc <= 25.0

    def test_improving_trend(self):
        """Declining CCC over history is classified as IMPROVING."""
        result = compute_working_capital_discipline(
            receivables=5_000.0,
            inventory=3_000.0,
            payables=4_000.0,
            revenue=80_000.0,
            cogs=50_000.0,
            history=[
                {"ccc": 55.0},
                {"ccc": 50.0},
                {"ccc": 42.0},
                {"ccc": 38.0},
            ],
        )
        assert result.ccc_trend == "IMPROVING"

    def test_missing_data(self):
        """None inputs return None metrics."""
        result = compute_working_capital_discipline(
            receivables=None,
            inventory=None,
            payables=None,
            revenue=None,
            cogs=None,
        )
        assert result.dso is None
        assert result.dio is None
        assert result.dpo is None
        assert result.ccc is None
        assert result.ccc_trend == "UNKNOWN"


# ── M&A Discipline Tests ────────────────────────────────────────────────


class TestMADiscipline:
    """Tests for assess_ma_discipline()."""

    def test_clean_record(self):
        """Company with 2 small acquisitions, no impairments."""
        acquisitions = [
            {"date": "2023-03-15", "value": 50.0, "is_significant": False, "had_impairment": False},
            {"date": "2024-01-20", "value": 80.0, "is_significant": False, "had_impairment": False},
        ]
        result = assess_ma_discipline(
            acquisitions,
            goodwill_history=[200.0, 210.0, 220.0, 230.0],
            total_assets_history=[2000.0, 2100.0, 2200.0, 2300.0],
        )
        assert isinstance(result, MADiscipline)
        assert result.acquisition_count == 2
        assert result.serial_acquirer is False
        assert result.impairment_count == 0
        assert result.goodwill_assets_ratio is not None
        assert result.goodwill_trend == "STABLE"

    def test_serial_acquirer_with_impairments(self):
        """Aggressive acquirer with goodwill blowups."""
        acquisitions = [
            {"date": "2022-01-01", "value": 500.0, "is_significant": True, "had_impairment": True},
            {"date": "2022-06-01", "value": 300.0, "is_significant": True, "had_impairment": False},
            {"date": "2023-01-01", "value": 700.0, "is_significant": True, "had_impairment": True},
            {"date": "2023-08-01", "value": 400.0, "is_significant": True, "had_impairment": False},
            {"date": "2024-02-01", "value": 250.0, "is_significant": True, "had_impairment": True},
        ]
        result = assess_ma_discipline(
            acquisitions,
            goodwill_history=[500.0, 800.0, 1200.0, 1800.0],
            total_assets_history=[3000.0, 3200.0, 3500.0, 4000.0],
        )
        assert result.serial_acquirer is True
        assert result.impairment_count == 3
        assert result.goodwill_trend == "GROWING"

    def test_no_acquisitions(self):
        """Organic grower with no M&A history."""
        result = assess_ma_discipline([])
        assert result.acquisition_count == 0
        assert result.serial_acquirer is False
        assert result.impairment_count == 0
        assert result.goodwill_assets_ratio is None


# ── Buyback Effectiveness Tests ──────────────────────────────────────────


class TestBuybackEffectiveness:
    """Tests for assess_buyback_effectiveness()."""

    def test_good_below_current_price(self):
        """Bought back shares below current price -> GOOD."""
        result = assess_buyback_effectiveness(
            shares_history=[1000.0, 980.0, 960.0, 940.0, 920.0],
            avg_repurchase_price=85.0,
            current_price=120.0,
            buyback_amount=500.0,
            market_cap=15_000.0,
        )
        assert isinstance(result, BuybackEffectiveness)
        assert result.shares_outstanding_trend == "DECREASING"
        assert result.shares_5y_change_pct < 0
        assert result.repurchase_vs_current == "GOOD"
        assert result.buyback_yield is not None
        assert result.buyback_yield > 3.0  # 500/15000 * 100 = 3.33

    def test_bad_above_current_price(self):
        """Overpaid on buybacks -> BAD."""
        result = assess_buyback_effectiveness(
            shares_history=[1000.0, 990.0, 985.0],
            avg_repurchase_price=150.0,
            current_price=100.0,
        )
        assert result.repurchase_vs_current == "BAD"


# ── Dividend Sustainability Tests ────────────────────────────────────────


class TestDividendSustainability:
    """Tests for assess_dividend_sustainability()."""

    def test_sustainable_dividend(self):
        """Payout well within earnings and FCF."""
        result = assess_dividend_sustainability(
            eps=5.00,
            fcf_per_share=6.00,
            dividend_per_share=2.00,
            total_dividends=800.0,
            total_fcf=2_400.0,
            consecutive_growth_years=15,
        )
        assert isinstance(result, DividendSustainability)
        assert result.eps_payout_ratio == 0.4  # 2/5
        assert result.fcf_payout_ratio is not None
        assert result.fcf_payout_ratio < 0.50
        assert result.fcf_coverage == 3.0  # 2400/800
        assert result.is_sustainable is True
        assert result.consecutive_growth_years == 15

    def test_unsustainable_dividend(self):
        """Payout > 100% of EPS -> unsustainable."""
        result = assess_dividend_sustainability(
            eps=1.50,
            fcf_per_share=1.80,
            dividend_per_share=2.00,
            total_dividends=1_000.0,
            total_fcf=900.0,
        )
        assert result.eps_payout_ratio is not None
        assert result.eps_payout_ratio > 1.0
        assert result.is_sustainable is False


# ── Capital Allocation Score Tests ───────────────────────────────────────


class TestCapitalAllocationScore:
    """Tests for compute_capital_allocation_score()."""

    def test_high_score(self):
        """Excellent capital allocator: strong FCF, disciplined M&A, good buybacks."""
        fcf = FCFConversion(ebitda_to_fcf_ratio=0.85, is_red_flag=False)
        wc = WorkingCapitalDiscipline(ccc_trend="IMPROVING")
        ma = MADiscipline(serial_acquirer=False, impairment_count=0)
        bb = BuybackEffectiveness(repurchase_vs_current="GOOD")
        div = DividendSustainability(is_sustainable=True, consecutive_growth_years=12)

        score = compute_capital_allocation_score(fcf, wc, ma, bb, div)
        # 50 + 25 + 10 + 10 + 7.5 + 10 + 5 = 117.5, capped at 100
        assert score >= 90.0

    def test_low_score(self):
        """Poor allocator: red-flag FCF, serial acquirer with impairments, bad buybacks."""
        fcf = FCFConversion(ebitda_to_fcf_ratio=0.35, is_red_flag=True)
        wc = WorkingCapitalDiscipline(ccc_trend="DETERIORATING")
        ma = MADiscipline(serial_acquirer=True, impairment_count=3)
        bb = BuybackEffectiveness(repurchase_vs_current="BAD")
        div = DividendSustainability(is_sustainable=False)

        score = compute_capital_allocation_score(fcf, wc, ma, bb, div)
        # 50 - 15 - 10 - 5 - 15 - 7.5 - 10 = negative, floored at 0
        assert score <= 20.0


# ── Orchestrator Tests ───────────────────────────────────────────────────


class TestAnalyzeCapitalAllocation:
    """Tests for analyze_capital_allocation() orchestrator."""

    def test_full_orchestration(self):
        """Full data produces complete CapitalAllocationResult."""
        data = {
            "ebitda": 8_000.0,
            "fcf": 6_800.0,
            "capex": -2_500.0,
            "depreciation": -1_500.0,
            "working_capital_change": -300.0,
            "revenue": 40_000.0,
            "cogs": 24_000.0,
            "receivables": 4_500.0,
            "inventory": 3_200.0,
            "payables": 5_100.0,
            "acquisitions": [
                {"date": "2023-06-01", "value": 200.0, "is_significant": False, "had_impairment": False},
            ],
            "goodwill_history": [1000.0, 1050.0, 1100.0],
            "total_assets_history": [12000.0, 12500.0, 13000.0],
            "shares_history": [500.0, 490.0, 480.0, 470.0, 460.0],
            "avg_repurchase_price": 75.0,
            "current_price": 95.0,
            "buyback_amount": 400.0,
            "market_cap": 44_000.0,
            "eps": 8.50,
            "fcf_per_share": 10.20,
            "dividend_per_share": 3.00,
            "total_dividends": 1_400.0,
            "total_fcf": 6_800.0,
            "consecutive_growth_years": 8,
            "wc_history": [
                {"ccc": 40.0},
                {"ccc": 38.0},
                {"ccc": 35.0},
                {"ccc": 33.0},
            ],
        }
        result = analyze_capital_allocation(data)
        assert isinstance(result, CapitalAllocationResult)
        assert result.fcf_conversion.ebitda_to_fcf_ratio == 0.85
        assert result.fcf_conversion.is_red_flag is False
        assert result.capex.growth_capex == 1_000.0
        assert result.working_capital.ccc is not None
        assert result.ma_discipline.acquisition_count == 1
        assert result.buybacks.repurchase_vs_current == "GOOD"
        assert result.dividends.is_sustainable is True
        assert 0.0 <= result.overall_score <= 100.0
