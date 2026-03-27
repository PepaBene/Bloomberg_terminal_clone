"""Tests for E3 Extension — Credit-Aware Financial Strength (FI Supplement)."""

import pytest

from src.engines.e3_composites import compute_credit_aware_financial_strength


# ── Full Input Tests ──────────────────────────────────────────────────


def test_strong_credit_aware_score():
    """Strong financial health across all components."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=85.0,
        ohlson_o_score=-2.0,   # very healthy → 90
        merton_dd=5.0,         # very safe → 95
        credit_momentum_score=0.5,  # improving → 70
    )
    assert result["score"] is not None
    assert result["score"] > 75.0
    assert result["classification"] == "STRONG"
    assert result["data_quality"] == "COMPLETE"


def test_distressed_credit_aware_score():
    """Distressed company: weak financials, high O-Score, low DD, deteriorating."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=15.0,
        ohlson_o_score=2.0,       # very risky → 10
        merton_dd=0.5,            # near default → 10
        credit_momentum_score=-0.8,  # deteriorating → 16
    )
    assert result["score"] is not None
    assert result["score"] < 25.0
    assert result["classification"] == "DISTRESSED"
    assert result["data_quality"] == "COMPLETE"


def test_adequate_mixed_signals():
    """Mixed signals → ADEQUATE classification."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=60.0,
        ohlson_o_score=0.3,      # moderate → 50
        merton_dd=2.5,           # moderate → 60
        credit_momentum_score=0.0,  # neutral → 50
    )
    assert result["score"] is not None
    assert 50.0 <= result["score"] <= 75.0
    assert result["classification"] == "ADEQUATE"


def test_weak_credit_quality():
    """Weak credit quality."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=30.0,
        ohlson_o_score=0.8,      # risky → 30
        merton_dd=1.5,           # moderate risk → 35
        credit_momentum_score=-0.4,  # deteriorating → 34
    )
    assert result["score"] is not None
    assert 25.0 <= result["score"] <= 50.0
    assert result["classification"] == "WEAK"


# ── Component Weight Tests ─────────────────────────────────────────────


def test_component_weights_sum_to_one():
    """All component weights should sum to 1.0."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=70.0,
        ohlson_o_score=-0.5,
        merton_dd=3.0,
        credit_momentum_score=0.2,
    )
    components = result["components"]
    total_weight = sum(c["weight"] for c in components.values())
    assert total_weight == pytest.approx(1.0, abs=1e-6)


def test_all_components_have_required_fields():
    """Each component should have raw, score, weight."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=70.0,
        ohlson_o_score=-0.5,
        merton_dd=3.0,
        credit_momentum_score=0.2,
    )
    for name, comp in result["components"].items():
        assert "raw" in comp, f"Missing 'raw' in {name}"
        assert "score" in comp, f"Missing 'score' in {name}"
        assert "weight" in comp, f"Missing 'weight' in {name}"


# ── Partial Input Tests ───────────────────────────────────────────────


def test_missing_one_component():
    """When one component is None, redistribute weights."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=80.0,
        ohlson_o_score=None,
        merton_dd=3.5,
        credit_momentum_score=0.3,
    )
    assert result["score"] is not None
    assert result["data_quality"] == "PARTIAL"
    # O-Score component should have score=None
    assert result["components"]["ohlson_o_score"]["score"] is None
    # Remaining weights should still sum to 1.0
    active_weights = sum(
        c["weight"] for c in result["components"].values() if c["score"] is not None
    )
    assert active_weights == pytest.approx(1.0, abs=1e-6)


def test_missing_multiple_components():
    """Only financial strength and Merton DD available."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=70.0,
        ohlson_o_score=None,
        merton_dd=2.5,
        credit_momentum_score=None,
    )
    assert result["score"] is not None
    assert result["data_quality"] == "PARTIAL"


def test_all_none_returns_none():
    """All inputs None → score is None."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=None,
        credit_momentum_score=None,
    )
    assert result["score"] is None
    assert result["classification"] is None
    assert result["data_quality"] == "INSUFFICIENT"


def test_only_financial_strength_available():
    """Only financial strength available — score equals it."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=65.0,
        ohlson_o_score=None,
        merton_dd=None,
        credit_momentum_score=None,
    )
    assert result["score"] == pytest.approx(65.0, abs=1.0)
    assert result["data_quality"] == "PARTIAL"


# ── O-Score Mapping Tests ────────────────────────────────────────────


def test_o_score_mapping_very_healthy():
    """O-Score < -1.0 → 90 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=-2.0,
        merton_dd=None,
        credit_momentum_score=None,
    )
    assert result["components"]["ohlson_o_score"]["score"] == 90.0


def test_o_score_mapping_risky():
    """O-Score > 1.0 → 10 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=2.0,
        merton_dd=None,
        credit_momentum_score=None,
    )
    assert result["components"]["ohlson_o_score"]["score"] == 10.0


# ── Merton DD Mapping Tests ─────────────────────────────────────────


def test_merton_dd_mapping_very_safe():
    """DD > 4.0 → 95 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=5.0,
        credit_momentum_score=None,
    )
    assert result["components"]["merton_dd"]["score"] == 95.0


def test_merton_dd_mapping_near_default():
    """DD < 1.0 → 10 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=0.5,
        credit_momentum_score=None,
    )
    assert result["components"]["merton_dd"]["score"] == 10.0


# ── Credit Momentum Mapping Tests ────────────────────────────────────


def test_credit_momentum_positive():
    """Positive momentum (+1.0) → 90 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=None,
        credit_momentum_score=1.0,
    )
    assert result["components"]["credit_momentum"]["score"] == pytest.approx(90.0, abs=1.0)


def test_credit_momentum_negative():
    """Negative momentum (-1.0) → 10 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=None,
        credit_momentum_score=-1.0,
    )
    assert result["components"]["credit_momentum"]["score"] == pytest.approx(10.0, abs=1.0)


def test_credit_momentum_neutral():
    """Neutral momentum (0.0) → 50 component score."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=None,
        ohlson_o_score=None,
        merton_dd=None,
        credit_momentum_score=0.0,
    )
    assert result["components"]["credit_momentum"]["score"] == pytest.approx(50.0, abs=1.0)


# ── Score Range Tests ────────────────────────────────────────────────


def test_score_bounded_0_to_100():
    """Score should always be in [0, 100] range."""
    result = compute_credit_aware_financial_strength(
        financial_strength_score=100.0,
        ohlson_o_score=-5.0,
        merton_dd=10.0,
        credit_momentum_score=1.0,
    )
    assert 0.0 <= result["score"] <= 100.0


def test_classification_boundaries():
    """Verify classification boundaries: STRONG>75, ADEQUATE 50-75, WEAK 25-50, DISTRESSED<25."""
    # Test near boundaries
    for fs, expected_class in [(90.0, "STRONG"), (60.0, "ADEQUATE"), (35.0, "WEAK"), (10.0, "DISTRESSED")]:
        result = compute_credit_aware_financial_strength(
            financial_strength_score=fs,
            ohlson_o_score=None,
            merton_dd=None,
            credit_momentum_score=None,
        )
        assert result["classification"] == expected_class, f"fs={fs}: expected {expected_class}, got {result['classification']}"
