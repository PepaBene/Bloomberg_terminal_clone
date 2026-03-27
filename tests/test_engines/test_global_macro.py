"""Tests for Pillar 3 Phase 3B — Global Macro Engine."""

import pytest

from src.engines.global_macro import (
    CENTRAL_BANKS,
    RECESSION_WEIGHTS,
    STANCE_KEYWORDS,
    CentralBankSnapshot,
    GlobalRateEnvironment,
    InflationComparison,
    RecessionIndicator,
    classify_inflation_trend,
    classify_policy_stance,
    compute_global_growth_ranking,
    compute_global_rate_environment,
    compute_inflation_comparison,
    compute_rate_differential,
    compute_recession_probability,
    detect_rate_surprise,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _g7_bank_data_tightening() -> list[dict]:
    """Mostly hiking central banks (tightening cycle)."""
    return [
        {"bank_code": "FED", "current_rate": 5.50, "last_action": "HIKE",
         "last_action_date": "2025-09-15", "rate_change_ytd_bps": 75},
        {"bank_code": "ECB", "current_rate": 4.50, "last_action": "HIKE",
         "last_action_date": "2025-09-10", "rate_change_ytd_bps": 50},
        {"bank_code": "BOE", "current_rate": 5.25, "last_action": "HIKE",
         "last_action_date": "2025-08-01", "rate_change_ytd_bps": 50},
        {"bank_code": "BOC", "current_rate": 5.00, "last_action": "HIKE",
         "last_action_date": "2025-07-15", "rate_change_ytd_bps": 25},
        {"bank_code": "RBA", "current_rate": 4.35, "last_action": "HIKE",
         "last_action_date": "2025-06-01", "rate_change_ytd_bps": 25},
        {"bank_code": "SNB", "current_rate": 1.75, "last_action": "HIKE",
         "last_action_date": "2025-06-15", "rate_change_ytd_bps": 25},
        {"bank_code": "BOJ", "current_rate": 0.10, "last_action": "HOLD",
         "last_action_date": "2025-09-20", "rate_change_ytd_bps": 0},
        {"bank_code": "PBOC", "current_rate": 3.45, "last_action": "CUT",
         "last_action_date": "2025-08-20", "rate_change_ytd_bps": -15},
        {"bank_code": "RBI", "current_rate": 6.50, "last_action": "HOLD",
         "last_action_date": "2025-08-10", "rate_change_ytd_bps": 0},
    ]


def _g7_inflation_data() -> list[dict]:
    """G7 inflation data with varied trends."""
    return [
        {"country": "US", "headline": 3.2, "core": 4.0,
         "history": [3.0, 3.1, 3.0, 3.1, 3.0, 3.2]},
        {"country": "UK", "headline": 6.8, "core": 6.9,
         "history": [8.0, 7.5, 7.2, 6.9, 6.8, 6.8]},
        {"country": "Japan", "headline": 3.3, "core": 3.1,
         "history": [2.5, 2.8, 3.0, 3.1, 3.2, 3.3]},
        {"country": "Germany", "headline": 4.5, "core": 5.0,
         "history": [5.5, 5.2, 5.0, 4.8, 4.6, 4.5]},
        {"country": "France", "headline": 4.0, "core": 3.8,
         "history": [4.2, 4.1, 4.0, 4.0, 4.0, 4.0]},
        {"country": "Canada", "headline": 3.5, "core": 3.3,
         "history": [3.8, 3.6, 3.5, 3.5, 3.5, 3.5]},
        {"country": "Italy", "headline": 5.5, "core": 5.0,
         "history": [6.0, 5.8, 5.6, 5.5, 5.5, 5.5]},
    ]


# ── TestPolicyStance ─────────────────────────────────────────────────────


class TestPolicyStance:
    """Tests for classify_policy_stance()."""

    def test_hawkish_from_hikes(self):
        """3 hikes, 0 cuts → HAWKISH."""
        changes = [
            {"action": "HIKE", "bps": 25},
            {"action": "HIKE", "bps": 25},
            {"action": "HIKE", "bps": 25},
        ]
        assert classify_policy_stance(changes) == "HAWKISH"

    def test_dovish_from_cuts(self):
        """2 cuts, 0 hikes → DOVISH."""
        changes = [
            {"action": "CUT", "bps": -25},
            {"action": "CUT", "bps": -50},
        ]
        assert classify_policy_stance(changes) == "DOVISH"

    def test_neutral_from_holds(self):
        """All holds → NEUTRAL."""
        changes = [
            {"action": "HOLD", "bps": 0},
            {"action": "HOLD", "bps": 0},
            {"action": "HOLD", "bps": 0},
        ]
        assert classify_policy_stance(changes) == "NEUTRAL"

    def test_keyword_override(self):
        """Keywords override action-based classification."""
        changes = [
            {"action": "HIKE", "bps": 25},
            {"action": "HIKE", "bps": 25},
        ]
        # Despite hikes, dovish keywords → DOVISH
        result = classify_policy_stance(changes, keywords=["rate cut expected"])
        assert result == "DOVISH"


# ── TestGlobalRateEnvironment ────────────────────────────────────────────


class TestGlobalRateEnvironment:
    """Tests for compute_global_rate_environment()."""

    def test_tightening_environment(self):
        """6 hiking / 1 cutting / 2 holding → TIGHTENING."""
        data = _g7_bank_data_tightening()
        result = compute_global_rate_environment(data)
        assert isinstance(result, GlobalRateEnvironment)
        assert result.hiking_count == 6
        assert result.cutting_count == 1
        assert result.holding_count == 2
        assert result.direction == "TIGHTENING"
        assert len(result.banks) == 9

    def test_all_holding_neutral(self):
        """All holding → NEUTRAL."""
        data = [
            {"bank_code": "FED", "current_rate": 5.50, "last_action": "HOLD",
             "last_action_date": "2025-09-15", "rate_change_ytd_bps": 0},
            {"bank_code": "ECB", "current_rate": 4.50, "last_action": "HOLD",
             "last_action_date": "2025-09-10", "rate_change_ytd_bps": 0},
            {"bank_code": "BOJ", "current_rate": -0.10, "last_action": "HOLD",
             "last_action_date": "2025-09-20", "rate_change_ytd_bps": 0},
        ]
        result = compute_global_rate_environment(data)
        assert result.direction == "NEUTRAL"
        assert result.holding_count == 3

    def test_majority_cutting_easing(self):
        """Majority cutting → EASING."""
        data = [
            {"bank_code": "FED", "current_rate": 4.50, "last_action": "CUT",
             "last_action_date": "2025-09-15", "rate_change_ytd_bps": -75},
            {"bank_code": "ECB", "current_rate": 3.50, "last_action": "CUT",
             "last_action_date": "2025-09-10", "rate_change_ytd_bps": -50},
            {"bank_code": "BOE", "current_rate": 4.25, "last_action": "CUT",
             "last_action_date": "2025-08-01", "rate_change_ytd_bps": -50},
            {"bank_code": "BOJ", "current_rate": -0.10, "last_action": "HOLD",
             "last_action_date": "2025-09-20", "rate_change_ytd_bps": 0},
        ]
        result = compute_global_rate_environment(data)
        assert result.direction == "EASING"
        assert result.cutting_count == 3


# ── TestInflationTrend ───────────────────────────────────────────────────


class TestInflationTrend:
    """Tests for classify_inflation_trend()."""

    def test_accelerating(self):
        """Latest >> prior 3-month avg → ACCELERATING."""
        values = [2.0, 2.1, 2.2, 2.1, 2.0, 2.8]
        assert classify_inflation_trend(values) == "ACCELERATING"

    def test_decelerating(self):
        """Latest << prior 3-month avg → DECELERATING."""
        values = [5.0, 4.8, 4.5, 4.2, 4.0, 3.5]
        assert classify_inflation_trend(values) == "DECELERATING"

    def test_stable(self):
        """Latest ~ prior 3-month avg → STABLE."""
        values = [3.0, 3.0, 3.1, 3.0, 3.0, 3.1]
        assert classify_inflation_trend(values) == "STABLE"

    def test_insufficient_data(self):
        """Fewer than 4 data points → STABLE."""
        assert classify_inflation_trend([3.0, 3.1, 3.2]) == "STABLE"


# ── TestInflationComparison ──────────────────────────────────────────────


class TestInflationComparison:
    """Tests for compute_inflation_comparison()."""

    def test_g7_comparison(self):
        """G7 inflation data → correct median and trend counts."""
        data = _g7_inflation_data()
        result = compute_inflation_comparison(data)
        assert isinstance(result, InflationComparison)
        assert len(result.country_data) == 7
        # Median of [3.2, 6.8, 3.3, 4.5, 4.0, 3.5, 5.5] = 4.0
        assert result.global_median_headline == 4.0
        # Check totals add up
        total = (result.countries_accelerating
                 + result.countries_decelerating
                 + result.countries_stable)
        assert total == 7

    def test_single_country(self):
        """Single country → median equals that country's headline."""
        data = [
            {"country": "US", "headline": 3.2, "core": 4.0,
             "history": [3.0, 3.1, 3.0, 3.1, 3.0, 3.2]},
        ]
        result = compute_inflation_comparison(data)
        assert result.global_median_headline == 3.2
        assert len(result.country_data) == 1


# ── TestRecessionProbability ─────────────────────────────────────────────


class TestRecessionProbability:
    """Tests for compute_recession_probability()."""

    def test_high_recession_risk(self):
        """Inverted curve + weak PMI + wide spreads → HIGH (80+)."""
        result = compute_recession_probability(
            yield_curve_spread=-0.8,
            pmi=44.0,
            credit_spreads_bps=600,
            unemployment_change=1.5,
        )
        assert isinstance(result, RecessionIndicator)
        assert result.probability >= 70
        assert result.classification == "HIGH"
        assert result.yield_curve_signal == "INVERTED"
        assert result.pmi_signal == "CONTRACTION"
        assert result.credit_signal == "STRESS"

    def test_low_recession_risk(self):
        """Normal curve + strong PMI + tight spreads → LOW."""
        result = compute_recession_probability(
            yield_curve_spread=1.5,
            pmi=56.0,
            credit_spreads_bps=150,
            unemployment_change=-0.2,
        )
        assert result.probability < 30
        assert result.classification == "LOW"
        assert result.yield_curve_signal == "NORMAL"
        assert result.pmi_signal == "EXPANSION"
        assert result.credit_signal == "NORMAL"

    def test_mixed_moderate(self):
        """Mixed signals → MODERATE or ELEVATED."""
        result = compute_recession_probability(
            yield_curve_spread=0.1,
            pmi=49.0,
            credit_spreads_bps=400,
        )
        assert 25 < result.probability < 65
        assert result.classification in ("MODERATE", "ELEVATED")

    def test_no_unemployment_data(self):
        """Missing unemployment → uses neutral assumption."""
        result = compute_recession_probability(
            yield_curve_spread=1.0,
            pmi=55.0,
            credit_spreads_bps=200,
            unemployment_change=None,
        )
        assert result.probability < 30
        assert result.classification == "LOW"


# ── TestGrowthRanking ────────────────────────────────────────────────────


class TestGrowthRanking:
    """Tests for compute_global_growth_ranking()."""

    def test_rank_g20(self):
        """Rank countries by GDP growth descending."""
        data = [
            {"country": "India", "gdp_growth": 6.5, "forecast": 6.8, "prior": 7.0},
            {"country": "US", "gdp_growth": 2.5, "forecast": 2.0, "prior": 2.1},
            {"country": "China", "gdp_growth": 5.2, "forecast": 5.0, "prior": 5.5},
            {"country": "Japan", "gdp_growth": 1.0, "forecast": 1.2, "prior": 1.7},
            {"country": "Germany", "gdp_growth": -0.1, "forecast": 0.5, "prior": 1.8},
        ]
        result = compute_global_growth_ranking(data)
        assert len(result) == 5
        assert result[0]["country"] == "India"
        assert result[0]["rank"] == 1
        assert result[-1]["country"] == "Germany"
        assert result[-1]["rank"] == 5

    def test_handle_ties(self):
        """Tied GDP growth → both ranked, stable order."""
        data = [
            {"country": "A", "gdp_growth": 3.0, "forecast": 3.0, "prior": 2.5},
            {"country": "B", "gdp_growth": 3.0, "forecast": 2.8, "prior": 2.9},
            {"country": "C", "gdp_growth": 1.0, "forecast": 1.5, "prior": 1.0},
        ]
        result = compute_global_growth_ranking(data)
        # First two tied at 3.0 → ranked 1 and 2
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2
        assert result[0]["gdp_growth"] == result[1]["gdp_growth"] == 3.0
        assert result[2]["rank"] == 3


# ── TestRateSurprise ─────────────────────────────────────────────────────


class TestRateSurprise:
    """Tests for detect_rate_surprise()."""

    def test_surprise_large_diff(self):
        """50bps actual vs 25bps expected → surprise."""
        assert detect_rate_surprise(25, 50) is True

    def test_no_surprise_exact(self):
        """25bps actual vs 25bps expected → no surprise."""
        assert detect_rate_surprise(25, 25) is False

    def test_surprise_opposite_direction(self):
        """Expected hike +25, actual cut -25 → |50| >= 25 → surprise."""
        assert detect_rate_surprise(25, -25) is True


# ── TestRateDifferential ─────────────────────────────────────────────────


class TestRateDifferential:
    """Tests for compute_rate_differential()."""

    def test_fed_vs_ecb(self):
        """FED 5.50 vs ECB 4.50 → +1.00."""
        diff = compute_rate_differential(5.50, 4.50)
        assert diff == pytest.approx(1.0)

    def test_same_rate(self):
        """Same rate → 0.0."""
        diff = compute_rate_differential(4.00, 4.00)
        assert diff == 0.0


# ── Integration Tests ────────────────────────────────────────────────────


class TestIntegration:
    """Full macro dashboard integration tests."""

    def test_full_g7_dashboard(self):
        """Complete G7 macro analysis pipeline."""
        # Rate environment
        rate_env = compute_global_rate_environment(_g7_bank_data_tightening())
        assert rate_env.direction == "TIGHTENING"

        # Inflation comparison
        inflation = compute_inflation_comparison(_g7_inflation_data())
        assert inflation.global_median_headline > 0
        assert len(inflation.country_data) == 7

        # Recession probability for US
        recession = compute_recession_probability(
            yield_curve_spread=-0.2,
            pmi=51.0,
            credit_spreads_bps=350,
            unemployment_change=0.3,
        )
        assert recession.classification in ("MODERATE", "ELEVATED")

        # Growth ranking
        gdp_data = [
            {"country": "US", "gdp_growth": 2.5, "forecast": 2.0, "prior": 2.1},
            {"country": "UK", "gdp_growth": 0.5, "forecast": 0.8, "prior": 4.0},
            {"country": "Japan", "gdp_growth": 1.0, "forecast": 1.2, "prior": 1.7},
        ]
        ranking = compute_global_growth_ranking(gdp_data)
        assert ranking[0]["country"] == "US"

    def test_easing_cycle_dashboard(self):
        """Easing cycle with low inflation and recession risk."""
        bank_data = [
            {"bank_code": "FED", "current_rate": 3.50, "last_action": "CUT",
             "last_action_date": "2025-12-15", "rate_change_ytd_bps": -100},
            {"bank_code": "ECB", "current_rate": 2.50, "last_action": "CUT",
             "last_action_date": "2025-12-10", "rate_change_ytd_bps": -75},
            {"bank_code": "BOE", "current_rate": 3.75, "last_action": "CUT",
             "last_action_date": "2025-11-01", "rate_change_ytd_bps": -50},
        ]
        rate_env = compute_global_rate_environment(bank_data)
        assert rate_env.direction == "EASING"
        assert rate_env.cutting_count == 3

        # Rate differential
        fed_rate = 3.50
        ecb_rate = 2.50
        diff = compute_rate_differential(fed_rate, ecb_rate)
        assert diff == pytest.approx(1.0)

        # Rate surprise
        assert detect_rate_surprise(25, 50) is True  # larger cut than expected

    def test_stagflation_scenario(self):
        """Stagflation: high inflation + recession signals."""
        inflation_data = [
            {"country": "US", "headline": 7.5, "core": 6.0,
             "history": [5.0, 5.5, 6.0, 6.5, 7.0, 7.5]},
            {"country": "UK", "headline": 9.0, "core": 7.0,
             "history": [6.0, 7.0, 7.5, 8.0, 8.5, 9.0]},
        ]
        inflation = compute_inflation_comparison(inflation_data)
        assert inflation.countries_accelerating == 2

        # Recession indicators worsen despite inflation
        recession = compute_recession_probability(
            yield_curve_spread=-0.5,
            pmi=46.0,
            credit_spreads_bps=450,
            unemployment_change=0.8,
        )
        assert recession.probability > 55
        assert recession.classification in ("ELEVATED", "HIGH")

    def test_policy_divergence(self):
        """Policy divergence: FED hawkish, ECB dovish."""
        fed_stance = classify_policy_stance([
            {"action": "HIKE", "bps": 25},
            {"action": "HIKE", "bps": 25},
        ])
        ecb_stance = classify_policy_stance([
            {"action": "CUT", "bps": -25},
            {"action": "CUT", "bps": -25},
        ])
        assert fed_stance == "HAWKISH"
        assert ecb_stance == "DOVISH"

        diff = compute_rate_differential(5.50, 3.50)
        assert diff == pytest.approx(2.0)
