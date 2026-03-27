"""Tests for Pillar 3 Phase 4C — Engine 4: Earnings Surprise Intelligence."""

import pytest

from src.engines.earnings_surprise_intelligence import (
    EPSAnalysis,
    EarningsSurpriseResult,
    GuidanceImplications,
    MarginAnalysis,
    RevenueAnalysis,
    RevisionImplication,
    StockReaction,
    analyze_earnings_event,
    analyze_eps_surprise,
    analyze_margin_performance,
    analyze_revenue_surprise,
    analyze_stock_reaction,
    assess_guidance_implications,
    compute_revision_implications,
    generate_key_takeaways,
    generate_narrative_template,
    generate_recommendation,
)


# ── analyze_eps_surprise Tests ───────────────────────────────────────────


class TestAnalyzeEpsSurprise:
    def test_eps_beat(self):
        result = analyze_eps_surprise(2.00, 2.20)
        assert result.beat is True
        assert result.surprise_pct > 0

    def test_eps_miss(self):
        result = analyze_eps_surprise(2.00, 1.80)
        assert result.beat is False
        assert result.surprise_pct < 0

    def test_eps_inline(self):
        result = analyze_eps_surprise(2.00, 2.01)
        assert result.magnitude == "inline"

    def test_eps_small_beat(self):
        result = analyze_eps_surprise(2.00, 2.10)
        assert result.magnitude == "small"

    def test_eps_large_beat(self):
        result = analyze_eps_surprise(2.00, 2.40)
        assert result.magnitude == "large"

    def test_eps_blowout_beat(self):
        result = analyze_eps_surprise(2.00, 2.60)
        assert result.magnitude == "blowout"

    def test_eps_blowout_miss(self):
        result = analyze_eps_surprise(2.00, 1.40)
        assert result.magnitude == "blowout"
        assert result.beat is False

    def test_zero_consensus(self):
        result = analyze_eps_surprise(0.0, 0.0)
        assert result.surprise_pct == 0.0

    def test_zero_consensus_nonzero_actual(self):
        result = analyze_eps_surprise(0.0, 1.0)
        assert result.surprise_pct == 100.0

    def test_returns_eps_analysis_dataclass(self):
        result = analyze_eps_surprise(2.00, 2.10)
        assert isinstance(result, EPSAnalysis)
        assert result.consensus == 2.00
        assert result.actual == 2.10

    def test_negative_eps_miss(self):
        result = analyze_eps_surprise(-0.50, -0.70)
        assert result.beat is False
        assert result.surprise_pct < 0


# ── analyze_revenue_surprise Tests ───────────────────────────────────────


class TestAnalyzeRevenueSurprise:
    def test_revenue_beat(self):
        result = analyze_revenue_surprise(10_000.0, 10_500.0)
        assert result.beat is True
        assert result.surprise_pct > 0

    def test_revenue_miss(self):
        result = analyze_revenue_surprise(10_000.0, 9_500.0)
        assert result.beat is False

    def test_revenue_inline(self):
        result = analyze_revenue_surprise(10_000.0, 10_050.0)
        assert result.magnitude == "inline"

    def test_revenue_small_beat(self):
        result = analyze_revenue_surprise(10_000.0, 10_200.0)
        assert result.magnitude == "small"

    def test_revenue_large_beat(self):
        result = analyze_revenue_surprise(10_000.0, 11_000.0)
        assert result.magnitude == "large"

    def test_revenue_blowout(self):
        result = analyze_revenue_surprise(10_000.0, 12_000.0)
        assert result.magnitude == "blowout"

    def test_zero_consensus(self):
        result = analyze_revenue_surprise(0.0, 0.0)
        assert result.surprise_pct == 0.0

    def test_returns_dataclass(self):
        result = analyze_revenue_surprise(10_000.0, 10_500.0)
        assert isinstance(result, RevenueAnalysis)


# ── analyze_margin_performance Tests ─────────────────────────────────────


class TestAnalyzeMarginPerformance:
    def test_expanding_margins(self):
        result = analyze_margin_performance(
            gross_margin=45.0, operating_margin=20.0,
            prior_gross_margin=43.0, prior_operating_margin=18.5,
        )
        assert result.margin_trend == "expanding"
        assert result.operating_margin_yoy_change == 1.5

    def test_contracting_margins(self):
        result = analyze_margin_performance(
            gross_margin=40.0, operating_margin=15.0,
            prior_gross_margin=42.0, prior_operating_margin=17.0,
        )
        assert result.margin_trend == "contracting"

    def test_stable_margins(self):
        result = analyze_margin_performance(
            gross_margin=40.0, operating_margin=15.0,
            prior_gross_margin=40.0, prior_operating_margin=15.2,
        )
        assert result.margin_trend == "stable"

    def test_no_prior_data(self):
        result = analyze_margin_performance(
            gross_margin=40.0, operating_margin=15.0,
        )
        assert result.margin_trend == "stable"
        assert result.gross_margin_yoy_change is None

    def test_all_none(self):
        result = analyze_margin_performance()
        assert isinstance(result, MarginAnalysis)
        assert result.margin_trend == "stable"

    def test_only_gross_margin_change(self):
        result = analyze_margin_performance(
            gross_margin=50.0, prior_gross_margin=48.0,
        )
        assert result.gross_margin_yoy_change == 2.0
        assert result.margin_trend == "expanding"


# ── assess_guidance_implications Tests ───────────────────────────────────


class TestAssessGuidanceImplications:
    def test_raised_guidance_positive(self):
        result = assess_guidance_implications("raised")
        assert result.confidence_level == "positive"

    def test_lowered_guidance_cautious(self):
        result = assess_guidance_implications("lowered")
        assert result.confidence_level == "cautious"

    def test_withdrawn_guidance_cautious(self):
        result = assess_guidance_implications("withdrawn")
        assert result.confidence_level == "cautious"

    def test_maintained_guidance_neutral(self):
        result = assess_guidance_implications("maintained")
        assert result.confidence_level == "neutral"

    def test_guidance_range_stored(self):
        result = assess_guidance_implications(
            "maintained", eps_low=2.0, eps_high=2.5,
            rev_low=10_000, rev_high=10_500,
        )
        assert result.eps_guidance_range == (2.0, 2.5)
        assert result.revenue_guidance_range == (10_000, 10_500)

    def test_guidance_vs_consensus_positive(self):
        result = assess_guidance_implications(
            "maintained", eps_low=2.20, eps_high=2.40,
            prior_eps_consensus=2.00,
        )
        assert result.confidence_level == "positive"

    def test_guidance_vs_consensus_cautious(self):
        result = assess_guidance_implications(
            "maintained", eps_low=1.60, eps_high=1.80,
            prior_eps_consensus=2.00,
        )
        assert result.confidence_level == "cautious"


# ── analyze_stock_reaction Tests ─────────────────────────────────────────


class TestAnalyzeStockReaction:
    def test_positive_reaction(self):
        result = analyze_stock_reaction(5.0, 2.0)
        assert result.reaction_type == "positive"

    def test_negative_reaction(self):
        result = analyze_stock_reaction(-5.0, 2.0)
        assert result.reaction_type == "negative"

    def test_neutral_reaction(self):
        result = analyze_stock_reaction(0.3, 1.0)
        assert result.reaction_type == "neutral"

    def test_muted_reaction_high_volume(self):
        result = analyze_stock_reaction(0.5, 2.5)
        assert result.reaction_type == "muted"

    def test_volatile_reaction(self):
        result = analyze_stock_reaction(-10.0, 4.0)
        assert result.reaction_type == "volatile"

    def test_returns_dataclass(self):
        result = analyze_stock_reaction(3.0, 1.5)
        assert isinstance(result, StockReaction)
        assert result.price_change_pct == 3.0
        assert result.volume_vs_avg == 1.5


# ── compute_revision_implications Tests ──────────────────────────────────


class TestComputeRevisionImplications:
    def test_strong_beat_upgrade(self):
        result = compute_revision_implications(15.0, 8.0, "maintained")
        assert result.direction == "upgrade"
        assert result.magnitude in ("moderate", "large")

    def test_strong_miss_downgrade(self):
        result = compute_revision_implications(-15.0, -8.0, "maintained")
        assert result.direction == "downgrade"

    def test_inline_maintain(self):
        result = compute_revision_implications(1.0, 0.5, "maintained")
        assert result.direction == "maintain"
        assert result.magnitude == "none"

    def test_raised_guidance_amplifies(self):
        result = compute_revision_implications(5.0, 3.0, "raised")
        assert result.direction == "upgrade"

    def test_lowered_guidance_forces_downgrade(self):
        result = compute_revision_implications(5.0, 3.0, "lowered")
        assert result.direction == "downgrade"

    def test_large_surprise_affects_all_periods(self):
        result = compute_revision_implications(20.0, 10.0, "raised")
        assert "full_year" in result.affected_periods

    def test_small_surprise_current_quarter_only(self):
        result = compute_revision_implications(4.0, 2.0, "maintained")
        if result.direction != "maintain":
            assert result.affected_periods == ["current_quarter"]

    def test_returns_dataclass(self):
        result = compute_revision_implications(5.0, 3.0)
        assert isinstance(result, RevisionImplication)


# ── generate_recommendation Tests ────────────────────────────────────────


class TestGenerateRecommendation:
    def test_strong_positive(self):
        eps = EPSAnalysis(2.0, 2.60, 30.0, True, "blowout")
        rev = RevenueAnalysis(10000, 11500, 15.0, True, "large")
        guidance = GuidanceImplications("raised", None, None, "positive")
        revision = RevisionImplication("upgrade", "large", ["full_year"])
        rec = generate_recommendation(eps, rev, guidance, revision)
        assert rec == "STRONG_POSITIVE"

    def test_strong_negative(self):
        eps = EPSAnalysis(2.0, 1.40, -30.0, False, "blowout")
        rev = RevenueAnalysis(10000, 8500, -15.0, False, "large")
        guidance = GuidanceImplications("withdrawn", None, None, "cautious")
        revision = RevisionImplication("downgrade", "large", ["full_year"])
        rec = generate_recommendation(eps, rev, guidance, revision)
        assert rec == "STRONG_NEGATIVE"

    def test_neutral_on_mixed(self):
        eps = EPSAnalysis(2.0, 2.05, 2.5, True, "inline")
        rev = RevenueAnalysis(10000, 9900, -1.0, False, "inline")
        guidance = GuidanceImplications("maintained", None, None, "neutral")
        revision = RevisionImplication("maintain", "none", [])
        rec = generate_recommendation(eps, rev, guidance, revision)
        assert rec == "NEUTRAL"

    def test_positive_on_moderate_beat(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10400, 4.0, True, "small")
        guidance = GuidanceImplications("raised", None, None, "positive")
        revision = RevisionImplication("upgrade", "small", ["current_quarter"])
        rec = generate_recommendation(eps, rev, guidance, revision)
        assert rec in ("POSITIVE", "STRONG_POSITIVE")


# ── generate_key_takeaways Tests ─────────────────────────────────────────


class TestGenerateKeyTakeaways:
    def test_includes_eps_takeaway(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        margin = MarginAnalysis(45.0, 20.0, 2.0, 1.5, "expanding")
        guidance = GuidanceImplications("raised", None, None, "positive")
        stock = StockReaction(3.0, 2.0, "positive")
        takeaways = generate_key_takeaways(eps, rev, margin, guidance, stock)
        assert any("EPS" in t for t in takeaways)

    def test_includes_revenue_takeaway(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        margin = MarginAnalysis()
        guidance = GuidanceImplications()
        stock = StockReaction()
        takeaways = generate_key_takeaways(eps, rev, margin, guidance, stock)
        assert any("Revenue" in t or "revenue" in t for t in takeaways)

    def test_max_five_takeaways(self):
        eps = EPSAnalysis(2.0, 2.60, 30.0, True, "blowout")
        rev = RevenueAnalysis(10000, 12000, 20.0, True, "blowout")
        margin = MarginAnalysis(50.0, 25.0, 3.0, 2.0, "expanding")
        guidance = GuidanceImplications("raised", None, None, "positive")
        stock = StockReaction(8.0, 3.0, "volatile")
        takeaways = generate_key_takeaways(eps, rev, margin, guidance, stock)
        assert len(takeaways) <= 5

    def test_includes_guidance_when_changed(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        margin = MarginAnalysis()
        guidance = GuidanceImplications("raised", None, None, "positive")
        stock = StockReaction()
        takeaways = generate_key_takeaways(eps, rev, margin, guidance, stock)
        assert any("guidance" in t.lower() for t in takeaways)

    def test_includes_stock_reaction(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        margin = MarginAnalysis()
        guidance = GuidanceImplications()
        stock = StockReaction(5.0, 2.0, "positive")
        takeaways = generate_key_takeaways(eps, rev, margin, guidance, stock)
        assert any("stock" in t.lower() or "reacted" in t.lower() for t in takeaways)


# ── generate_narrative_template Tests ────────────────────────────────────


class TestGenerateNarrativeTemplate:
    def test_beat_narrative(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        narrative = generate_narrative_template(eps, rev, "POSITIVE")
        assert "beat" in narrative
        assert "POSITIVE" in narrative

    def test_miss_narrative(self):
        eps = EPSAnalysis(2.0, 1.80, -10.0, False, "small")
        rev = RevenueAnalysis(10000, 9500, -5.0, False, "small")
        narrative = generate_narrative_template(eps, rev, "NEGATIVE")
        assert "missed" in narrative
        assert "NEGATIVE" in narrative

    def test_includes_eps_values(self):
        eps = EPSAnalysis(2.0, 2.20, 10.0, True, "small")
        rev = RevenueAnalysis(10000, 10500, 5.0, True, "small")
        narrative = generate_narrative_template(eps, rev, "POSITIVE")
        assert "$2.20" in narrative
        assert "$2.00" in narrative


# ── analyze_earnings_event Tests ─────────────────────────────────────────


class TestAnalyzeEarningsEvent:
    def test_full_analysis(self):
        result = analyze_earnings_event(
            eps_consensus=2.00,
            eps_actual=2.30,
            revenue_consensus=10_000.0,
            revenue_actual=10_500.0,
            gross_margin=45.0,
            operating_margin=20.0,
            prior_gross_margin=43.0,
            prior_operating_margin=18.5,
            guidance_direction="raised",
            eps_guidance_low=2.40,
            eps_guidance_high=2.60,
            price_change_pct=5.0,
            volume_vs_avg=2.5,
        )
        assert isinstance(result, EarningsSurpriseResult)
        assert result.eps_analysis.beat is True
        assert result.revenue_analysis.beat is True
        assert result.recommendation in (
            "STRONG_POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "STRONG_NEGATIVE",
        )
        assert len(result.key_takeaways) > 0
        assert len(result.narrative) > 0

    def test_miss_analysis(self):
        result = analyze_earnings_event(
            eps_consensus=2.00,
            eps_actual=1.60,
            revenue_consensus=10_000.0,
            revenue_actual=9_200.0,
            guidance_direction="lowered",
            price_change_pct=-8.0,
            volume_vs_avg=3.0,
        )
        assert result.eps_analysis.beat is False
        assert result.revenue_analysis.beat is False
        assert result.recommendation in ("NEGATIVE", "STRONG_NEGATIVE")

    def test_minimal_inputs(self):
        result = analyze_earnings_event(
            eps_consensus=2.00,
            eps_actual=2.10,
            revenue_consensus=10_000.0,
            revenue_actual=10_100.0,
        )
        assert isinstance(result, EarningsSurpriseResult)
        assert result.margin_analysis.margin_trend == "stable"

    def test_guidance_withdrawal(self):
        result = analyze_earnings_event(
            eps_consensus=2.00,
            eps_actual=2.00,
            revenue_consensus=10_000.0,
            revenue_actual=10_000.0,
            guidance_direction="withdrawn",
        )
        assert result.guidance.confidence_level == "cautious"

    def test_all_components_populated(self):
        result = analyze_earnings_event(
            eps_consensus=3.00,
            eps_actual=3.50,
            revenue_consensus=15_000.0,
            revenue_actual=15_800.0,
        )
        assert result.eps_analysis is not None
        assert result.revenue_analysis is not None
        assert result.margin_analysis is not None
        assert result.guidance is not None
        assert result.stock_reaction is not None
        assert result.revision_implication is not None
        assert result.recommendation is not None
        assert result.key_takeaways is not None
        assert result.narrative is not None
