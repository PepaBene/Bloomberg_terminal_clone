"""Tests for Pillar 3 Phase 2 -- Part 3: Earnings Surprise Engine."""

import pytest

from src.engines.earnings_surprise_engine import (
    GuidanceAnalysis,
    GuidanceCredibility,
    HistoricalPattern,
    MarketReactionAnalysis,
    SurpriseResult,
    analyze_market_reaction,
    classify_guidance,
    compute_all_surprises,
    compute_guidance_credibility,
    compute_historical_pattern,
    compute_surprise,
)


# ── TestComputeSurprise ────────────────────────────────────────────────────


class TestComputeSurprise:
    """Tests for compute_surprise()."""

    def test_beat_positive_surprise(self):
        # Actual EPS $3.42 vs consensus $3.17 = 7.89% beat
        result = compute_surprise(3.42, 3.17)
        assert result is not None
        assert result > 0
        assert abs(result - 7.8864) < 0.1

    def test_miss_negative_surprise(self):
        # Actual EPS $2.80 vs consensus $3.10 = -9.68% miss
        result = compute_surprise(2.80, 3.10)
        assert result is not None
        assert result < 0

    def test_zero_consensus_returns_none(self):
        result = compute_surprise(1.50, 0.0)
        assert result is None

    def test_none_inputs_return_none(self):
        assert compute_surprise(None, 3.17) is None
        assert compute_surprise(3.42, None) is None
        assert compute_surprise(None, None) is None

    def test_exact_match_zero_surprise(self):
        result = compute_surprise(5.20, 5.20)
        assert result is not None
        assert result == 0.0


# ── TestComputeAllSurprises ────────────────────────────────────────────────


class TestComputeAllSurprises:
    """Tests for compute_all_surprises()."""

    def test_all_beat(self):
        result = compute_all_surprises(
            actual_eps=3.42, consensus_eps=3.17,          # +7.89%
            actual_revenue=12.3e9, consensus_revenue=11.8e9,  # +4.24%
            actual_ebitda=4.1e9, consensus_ebitda=3.9e9,      # +5.13%
        )
        assert isinstance(result, SurpriseResult)
        assert result.is_beat is True
        assert result.is_miss is False
        assert result.eps_surprise_pct > 0
        assert result.revenue_surprise_pct > 0
        assert result.ebitda_surprise_pct > 0

    def test_all_miss(self):
        result = compute_all_surprises(
            actual_eps=2.80, consensus_eps=3.10,
            actual_revenue=10.5e9, consensus_revenue=11.2e9,
            actual_ebitda=3.2e9, consensus_ebitda=3.6e9,
        )
        assert result.is_miss is True
        assert result.is_beat is False
        assert result.eps_surprise_pct < 0
        assert result.revenue_surprise_pct < 0

    def test_mixed_results(self):
        # EPS beat, revenue miss, EBITDA beat -> majority beat
        result = compute_all_surprises(
            actual_eps=3.42, consensus_eps=3.17,
            actual_revenue=10.5e9, consensus_revenue=11.2e9,
            actual_ebitda=4.0e9, consensus_ebitda=3.8e9,
        )
        assert result.is_beat is True
        assert result.eps_surprise_pct > 0
        assert result.revenue_surprise_pct < 0

    def test_partial_data(self):
        # Only EPS available
        result = compute_all_surprises(
            actual_eps=3.42, consensus_eps=3.17,
        )
        assert result.eps_surprise_pct is not None
        assert result.revenue_surprise_pct is None
        assert result.ebitda_surprise_pct is None
        assert result.is_beat is True


# ── TestAnalyzeMarketReaction ──────────────────────────────────────────────


class TestAnalyzeMarketReaction:
    """Tests for analyze_market_reaction()."""

    def test_beat_and_rose(self):
        # 8% EPS beat, stock up 5% next day
        result = analyze_market_reaction(8.0, 5.0, 6.5)
        assert isinstance(result, MarketReactionAnalysis)
        assert result.beat_and_fell is False
        assert result.price_reaction_1d_pct == 5.0
        assert result.price_reaction_5d_pct == 6.5

    def test_beat_and_fell(self):
        # 5% beat but stock dropped 3%
        result = analyze_market_reaction(5.0, -3.0, -2.0)
        assert result.beat_and_fell is True

    def test_miss_and_fell(self):
        # -8% miss, stock down 6%
        result = analyze_market_reaction(-8.0, -6.0, -7.5)
        assert result.beat_and_fell is False
        assert result.price_reaction_1d_pct == -6.0

    def test_muted_reaction(self):
        # Large surprise but minimal price movement
        result = analyze_market_reaction(10.0, 0.2, 0.3)
        assert result.reaction_vs_surprise == "MUTED"

    def test_proportional_reaction(self):
        # Small surprise, moderate price move
        result = analyze_market_reaction(3.0, 2.5, 3.0)
        assert result.reaction_vs_surprise == "PROPORTIONAL"

    def test_none_inputs(self):
        result = analyze_market_reaction(None, None, None)
        assert isinstance(result, MarketReactionAnalysis)
        assert result.price_reaction_1d_pct == 0.0
        assert result.price_reaction_5d_pct == 0.0
        assert result.beat_and_fell is False


# ── TestComputeHistoricalPattern ───────────────────────────────────────────


class TestComputeHistoricalPattern:
    """Tests for compute_historical_pattern()."""

    def test_consecutive_beats(self):
        # 6 consecutive beats with moderate surprise
        surprises = [
            {"surprise_pct": 5.2, "guidance_midpoint": 3.10, "actual": 3.26},
            {"surprise_pct": 3.8, "guidance_midpoint": 2.95, "actual": 3.06},
            {"surprise_pct": 6.1, "guidance_midpoint": 2.80, "actual": 2.97},
            {"surprise_pct": 4.5, "guidance_midpoint": 2.65, "actual": 2.77},
            {"surprise_pct": 7.0, "guidance_midpoint": 2.50, "actual": 2.68},
            {"surprise_pct": 3.2, "guidance_midpoint": 2.40, "actual": 2.48},
        ]
        result = compute_historical_pattern(surprises)
        assert result.consecutive_beats == 6
        assert result.consecutive_misses == 0
        assert result.avg_surprise_magnitude_4q > 0

    def test_consecutive_misses(self):
        surprises = [
            {"surprise_pct": -3.5, "guidance_midpoint": 3.00, "actual": 2.90},
            {"surprise_pct": -5.0, "guidance_midpoint": 3.10, "actual": 2.95},
            {"surprise_pct": -2.1, "guidance_midpoint": 3.20, "actual": 3.13},
        ]
        result = compute_historical_pattern(surprises)
        assert result.consecutive_misses == 3
        assert result.consecutive_beats == 0

    def test_sandbagging_detection(self):
        # 4+ consecutive beats with >5% average magnitude = sandbagging
        surprises = [
            {"surprise_pct": 8.0, "guidance_midpoint": 3.00, "actual": 3.24},
            {"surprise_pct": 7.5, "guidance_midpoint": 2.90, "actual": 3.12},
            {"surprise_pct": 6.0, "guidance_midpoint": 2.80, "actual": 2.97},
            {"surprise_pct": 9.0, "guidance_midpoint": 2.70, "actual": 2.94},
        ]
        result = compute_historical_pattern(surprises)
        assert result.sandbagging_flag is True
        assert result.consecutive_beats == 4

    def test_mixed_pattern(self):
        # Beat then miss -- consecutive_beats = 1
        surprises = [
            {"surprise_pct": 3.0, "guidance_midpoint": 3.00, "actual": 3.09},
            {"surprise_pct": -2.0, "guidance_midpoint": 3.10, "actual": 3.04},
            {"surprise_pct": 5.0, "guidance_midpoint": 2.90, "actual": 3.05},
        ]
        result = compute_historical_pattern(surprises)
        assert result.consecutive_beats == 1
        assert result.consecutive_misses == 0

    def test_empty_history(self):
        result = compute_historical_pattern([])
        assert result.consecutive_beats == 0
        assert result.consecutive_misses == 0
        assert result.sandbagging_flag is False
        assert result.guidance_accuracy == 0.0


# ── TestClassifyGuidance ───────────────────────────────────────────────────


class TestClassifyGuidance:
    """Tests for classify_guidance()."""

    def test_initial_guidance(self):
        # New guidance with no prior
        result = classify_guidance(
            guidance_low=5.20, guidance_high=5.40,
            prior_low=None, prior_high=None,
            consensus=5.25,
        )
        assert result.guidance_type == "INITIAL"
        assert result.width_pct > 0

    def test_raised_guidance(self):
        # Both low and high increased
        result = classify_guidance(
            guidance_low=5.40, guidance_high=5.60,
            prior_low=5.20, prior_high=5.40,
            consensus=5.30,
        )
        assert result.guidance_type == "RAISED"
        assert result.guidance_vs_consensus == "ABOVE"

    def test_lowered_guidance(self):
        # Both low and high decreased
        result = classify_guidance(
            guidance_low=4.80, guidance_high=5.00,
            prior_low=5.20, prior_high=5.40,
            consensus=5.30,
        )
        assert result.guidance_type == "LOWERED"
        assert result.guidance_vs_consensus == "BELOW"

    def test_narrowed_guidance(self):
        # Range narrowed significantly
        result = classify_guidance(
            guidance_low=5.25, guidance_high=5.35,
            prior_low=5.00, prior_high=5.60,
            consensus=5.30,
        )
        assert result.guidance_type == "NARROWED"

    def test_maintained_guidance(self):
        # Essentially unchanged (within 1%)
        result = classify_guidance(
            guidance_low=5.20, guidance_high=5.40,
            prior_low=5.20, prior_high=5.40,
            consensus=5.30,
        )
        assert result.guidance_type == "MAINTAINED"
        assert result.guidance_vs_consensus == "INLINE"

    def test_withdrawn_guidance(self):
        # Company withdrew guidance
        result = classify_guidance(
            guidance_low=None, guidance_high=None,
            prior_low=5.20, prior_high=5.40,
            consensus=5.30,
        )
        assert result.guidance_type == "WITHDRAWN"

    def test_vs_consensus_above(self):
        # Midpoint well above consensus
        result = classify_guidance(
            guidance_low=5.50, guidance_high=5.70,
            prior_low=None, prior_high=None,
            consensus=5.20,
        )
        assert result.guidance_vs_consensus == "ABOVE"

    def test_vs_consensus_below(self):
        # Midpoint well below consensus
        result = classify_guidance(
            guidance_low=4.80, guidance_high=5.00,
            prior_low=None, prior_high=None,
            consensus=5.30,
        )
        assert result.guidance_vs_consensus == "BELOW"

    def test_width_calculation(self):
        result = classify_guidance(
            guidance_low=5.00, guidance_high=5.50,
            prior_low=None, prior_high=None,
            consensus=5.25,
        )
        # Width = (5.50 - 5.00) / ((5.00+5.50)/2) * 100 = 0.50 / 5.25 * 100 ~ 9.52%
        assert result.width_pct > 9.0
        assert result.width_pct < 10.0


# ── TestComputeGuidanceCredibility ─────────────────────────────────────────


class TestComputeGuidanceCredibility:
    """Tests for compute_guidance_credibility()."""

    def test_high_accuracy(self):
        # Guidance very close to actuals
        history = [
            {"guidance_midpoint": 3.20, "actual": 3.22, "guidance_low": 3.10, "guidance_high": 3.30},
            {"guidance_midpoint": 3.00, "actual": 3.02, "guidance_low": 2.90, "guidance_high": 3.10},
            {"guidance_midpoint": 2.85, "actual": 2.87, "guidance_low": 2.75, "guidance_high": 2.95},
            {"guidance_midpoint": 2.70, "actual": 2.72, "guidance_low": 2.60, "guidance_high": 2.80},
        ]
        result = compute_guidance_credibility(history)
        assert isinstance(result, GuidanceCredibility)
        assert result.credibility_score > 70
        assert result.historical_accuracy > 0.9

    def test_low_accuracy(self):
        # Guidance systematically far off from actuals (30-50% errors)
        history = [
            {"guidance_midpoint": 3.00, "actual": 4.50, "guidance_low": 2.50, "guidance_high": 3.50},
            {"guidance_midpoint": 2.80, "actual": 4.20, "guidance_low": 2.30, "guidance_high": 3.30},
            {"guidance_midpoint": 2.60, "actual": 4.00, "guidance_low": 2.10, "guidance_high": 3.10},
            {"guidance_midpoint": 2.50, "actual": 3.80, "guidance_low": 2.00, "guidance_high": 3.00},
        ]
        result = compute_guidance_credibility(history)
        assert result.credibility_score < 60
        assert result.historical_accuracy < 0.70

    def test_no_history(self):
        result = compute_guidance_credibility([])
        assert result.credibility_score == 0.0
        assert result.historical_accuracy == 0.0

    def test_single_quarter(self):
        history = [
            {"guidance_midpoint": 3.20, "actual": 3.25, "guidance_low": 3.10, "guidance_high": 3.30},
        ]
        result = compute_guidance_credibility(history)
        assert result.credibility_score > 0
        assert result.historical_accuracy > 0.9
        # Single quarter gets moderate consistency (0.5)
        assert result.consistency_score == 0.5


# ── TestEdgeCases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests across multiple functions."""

    def test_negative_eps_surprise(self):
        # Company with negative EPS: actual -$0.50 vs consensus -$0.80
        result = compute_surprise(-0.50, -0.80)
        assert result is not None
        # (-0.50 - (-0.80)) / abs(-0.80) * 100 = 0.30/0.80*100 = 37.5%
        assert result > 0  # Less negative than expected = beat

    def test_overreaction_classification(self):
        # Small surprise but huge price move
        result = analyze_market_reaction(1.0, 15.0, 12.0)
        assert result.reaction_vs_surprise == "OVERREACTION"

    def test_guidance_credibility_no_width_data(self):
        # History without guidance_low/guidance_high
        history = [
            {"guidance_midpoint": 3.20, "actual": 3.22},
            {"guidance_midpoint": 3.00, "actual": 3.05},
        ]
        result = compute_guidance_credibility(history)
        assert result.credibility_score > 0
        assert result.avg_width_pct == 0.0

    def test_historical_pattern_guidance_accuracy(self):
        surprises = [
            {"surprise_pct": 5.0, "guidance_midpoint": 3.10, "actual": 3.15},
            {"surprise_pct": 3.0, "guidance_midpoint": 2.95, "actual": 3.00},
        ]
        result = compute_historical_pattern(surprises)
        assert result.guidance_accuracy > 0.9
