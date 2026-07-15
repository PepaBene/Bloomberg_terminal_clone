"""Tests for the Composite Risk Profile Engine."""

from src.engines.risk_profile_engine import (
    RiskFactor,
    RiskProfileResult,
    assess_risk_profile,
    classify_overall_risk_tier,
    compute_credit_risk_score,
    compute_data_completeness,
    compute_earnings_quality_risk_score,
    compute_market_risk_score,
    compute_overall_risk_score,
)


# ── Sub-score tests ───────────────────────────────────────────────────────


class TestComputeCreditRiskScore:
    """Tests for compute_credit_risk_score()."""

    def test_all_inputs_missing_returns_none(self):
        assert compute_credit_risk_score({}) is None

    def test_safe_low_leverage_low_refi_scores_low(self):
        signals = {
            "z_score": 3.5,
            "net_debt_ebitda": 1.0,
            "refinancing_risk_score": 10.0,
        }
        score = compute_credit_risk_score(signals)
        assert score is not None
        assert score < 25.0

    def test_distress_high_leverage_high_refi_scores_high(self):
        signals = {
            "z_score": 1.0,
            "net_debt_ebitda": 7.5,
            "refinancing_risk_score": 90.0,
        }
        score = compute_credit_risk_score(signals)
        assert score is not None
        assert score > 75.0

    def test_partial_inputs_still_scores(self):
        """Only z_score present -- still produces a score from that alone."""
        score = compute_credit_risk_score({"z_score": 1.0})
        assert score is not None
        assert score == 100.0  # distress zone, fully weighted on the sole input


class TestComputeEarningsQualityRiskScore:
    """Tests for compute_earnings_quality_risk_score()."""

    def test_all_inputs_missing_returns_none(self):
        assert compute_earnings_quality_risk_score({}) is None

    def test_strong_fundamentals_scores_low(self):
        signals = {
            "piotroski_f_score": 8.0,
            "beneish_m_score": -2.8,
            "accruals_quality": 0.10,
        }
        score = compute_earnings_quality_risk_score(signals)
        assert score is not None
        assert score < 25.0

    def test_weak_fundamentals_scores_high(self):
        signals = {
            "piotroski_f_score": 2.0,
            "beneish_m_score": -1.0,
            "accruals_quality": 0.85,
        }
        score = compute_earnings_quality_risk_score(signals)
        assert score is not None
        assert score > 75.0


class TestComputeMarketRiskScore:
    """Tests for compute_market_risk_score()."""

    def test_all_inputs_missing_returns_none(self):
        assert compute_market_risk_score({}) is None

    def test_low_beta_low_vol_scores_low(self):
        signals = {"beta": 0.6, "annualized_volatility": 0.15}
        score = compute_market_risk_score(signals)
        assert score is not None
        assert score < 25.0

    def test_high_beta_high_vol_scores_high(self):
        signals = {"beta": 2.2, "annualized_volatility": 0.65}
        score = compute_market_risk_score(signals)
        assert score is not None
        assert score >= 100.0


class TestComputeOverallRiskScore:
    """Tests for compute_overall_risk_score()."""

    def test_all_none_returns_none(self):
        assert compute_overall_risk_score(None, None, None) is None

    def test_single_available_subscore_is_used_directly(self):
        """Renormalization over a single available sub-score should return
        that sub-score's value unchanged (weight renormalizes to 1.0)."""
        result = compute_overall_risk_score(80.0, None, None)
        assert result == 80.0

    def test_two_available_subscores_renormalized(self):
        # credit=0.40, market=0.30 -> renormalized weights 4/7 and 3/7
        result = compute_overall_risk_score(100.0, None, 0.0)
        assert result is not None
        assert 0.0 < result < 100.0


class TestClassifyOverallRiskTier:
    """Tests for classify_overall_risk_tier()."""

    def test_none_is_unknown(self):
        assert classify_overall_risk_tier(None) == "UNKNOWN"

    def test_bands(self):
        assert classify_overall_risk_tier(10.0) == "LOW"
        assert classify_overall_risk_tier(30.0) == "MODERATE"
        assert classify_overall_risk_tier(60.0) == "ELEVATED"
        assert classify_overall_risk_tier(90.0) == "HIGH"


class TestComputeDataCompleteness:
    """Tests for compute_data_completeness()."""

    def test_empty_signals_is_zero(self):
        assert compute_data_completeness({}) == 0.0

    def test_all_eight_present_is_one(self):
        signals = {
            "z_score": 3.0,
            "piotroski_f_score": 7.0,
            "beneish_m_score": -2.5,
            "accruals_quality": 0.3,
            "net_debt_ebitda": 2.0,
            "refinancing_risk_score": 20.0,
            "beta": 1.0,
            "annualized_volatility": 0.25,
        }
        assert compute_data_completeness(signals) == 1.0

    def test_partial_fraction(self):
        signals = {"z_score": 3.0, "beta": 1.0}
        assert compute_data_completeness(signals) == 0.25  # 2/8


# ── Orchestrator tests ────────────────────────────────────────────────────


class TestAssessRiskProfile:
    """Tests for assess_risk_profile() orchestrator."""

    def test_healthy_company_fully_populated(self):
        """Strong Z-score, high Piotroski, low leverage, low beta/vol."""
        signals = {
            "z_score": 4.2,
            "piotroski_f_score": 8.0,
            "beneish_m_score": -2.9,
            "accruals_quality": 0.05,
            "net_debt_ebitda": 0.8,
            "refinancing_risk_score": 8.0,
            "beta": 0.85,
            "annualized_volatility": 0.16,
        }
        result = assess_risk_profile(signals)
        assert isinstance(result, RiskProfileResult)
        assert result.credit_risk_score is not None
        assert result.earnings_quality_risk_score is not None
        assert result.market_risk_score is not None
        assert result.overall_risk_score is not None
        assert result.overall_risk_tier == "LOW"
        assert len(result.risk_factors) == 0
        assert result.data_completeness == 1.0

    def test_distressed_company_fully_populated(self):
        """Z-score in distress zone, low Piotroski, high Beneish, high leverage."""
        signals = {
            "z_score": 1.2,
            "piotroski_f_score": 1.0,
            "beneish_m_score": -1.2,
            "accruals_quality": 0.9,
            "net_debt_ebitda": 8.0,
            "refinancing_risk_score": 85.0,
            "beta": 2.4,
            "annualized_volatility": 0.70,
        }
        result = assess_risk_profile(signals)
        assert result.overall_risk_tier in {"ELEVATED", "HIGH"}
        assert len(result.risk_factors) > 1
        assert result.data_completeness == 1.0
        # Sanity: high-severity factors should be present
        severities = {f.severity for f in result.risk_factors}
        assert "HIGH" in severities

    def test_partial_signals_only_credit_inputs(self):
        """Only credit-risk inputs present; earnings-quality and market-risk None."""
        signals = {
            "z_score": 2.5,
            "net_debt_ebitda": 3.0,
            "refinancing_risk_score": 40.0,
        }
        result = assess_risk_profile(signals)
        assert result.credit_risk_score is not None
        assert result.earnings_quality_risk_score is None
        assert result.market_risk_score is None
        assert result.overall_risk_score is not None
        assert result.overall_risk_score == result.credit_risk_score
        assert result.data_completeness == 3 / 8

    def test_completely_empty_signals(self):
        """Empty signals dict never crashes and reports UNKNOWN/empty."""
        result = assess_risk_profile({})
        assert result.credit_risk_score is None
        assert result.earnings_quality_risk_score is None
        assert result.market_risk_score is None
        assert result.overall_risk_score is None
        assert result.overall_risk_tier == "UNKNOWN"
        assert result.data_completeness == 0.0
        assert result.risk_factors == []

    def test_specific_risk_factor_content_z_score_distress(self):
        """Hand-constructed triggering case: verify exact factor content,
        not just non-empty list."""
        signals = {"z_score": 1.5}
        result = assess_risk_profile(signals)
        assert len(result.risk_factors) == 1
        factor = result.risk_factors[0]
        assert isinstance(factor, RiskFactor)
        assert factor.metric == "z_score"
        assert factor.severity == "HIGH"
        assert factor.value == 1.5
        assert factor.factor == "Altman Z-Score of 1.50 is in the distress zone (< 1.81)"

    def test_specific_risk_factor_content_net_debt_ebitda_moderate(self):
        """Leverage just above the 4.0x elevated threshold triggers MODERATE."""
        signals = {"net_debt_ebitda": 4.5}
        result = assess_risk_profile(signals)
        assert len(result.risk_factors) == 1
        factor = result.risk_factors[0]
        assert factor.metric == "net_debt_ebitda"
        assert factor.severity == "MODERATE"
        assert factor.value == 4.5
        assert factor.factor == "Net debt/EBITDA of 4.50x is elevated (> 4.0x)"
