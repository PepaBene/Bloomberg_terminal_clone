"""Tests for E15 Cross-Asset Divergence Signals Engine."""

import pytest

from src.engines.e15_cross_asset import (
    SIGNAL_TYPES,
    compute_cross_asset_regime,
    compute_equity_exposure_adjustment,
    detect_divergence_signals,
)


# ── Signal Detection Tests ───────────────────────────────────────────


def test_signal_equity_rally_bond_deterioration():
    """Detect signal when equity rallies but bonds deteriorate."""
    equity = {"return_3m": 0.20, "return_6m": 0.25}
    bond = {"spread_bps": 300.0, "spread_change_3m_bps": 80.0, "spread_percentile": 60.0}

    signals = detect_divergence_signals(equity, bond)
    types = [s["signal_type"] for s in signals]
    assert "EQUITY_RALLY_BOND_DETERIORATION" in types

    sig = next(s for s in signals if s["signal_type"] == "EQUITY_RALLY_BOND_DETERIORATION")
    assert sig["severity"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= sig["confidence"] <= 1.0


def test_signal_bond_distress_before_equity():
    """Detect signal when bonds show distress but equity hasn't repriced."""
    equity = {"return_3m": 0.02, "return_6m": 0.05}
    bond = {"spread_bps": 600.0, "spread_change_3m_bps": 250.0, "spread_percentile": 90.0}

    signals = detect_divergence_signals(equity, bond)
    types = [s["signal_type"] for s in signals]
    assert "BOND_DISTRESS_BEFORE_EQUITY" in types

    sig = next(s for s in signals if s["signal_type"] == "BOND_DISTRESS_BEFORE_EQUITY")
    assert sig["severity"] == "HIGH"


def test_signal_fallen_angel_overhang():
    """Detect fallen angel overhang for BBB issuer with negative outlook and high vol."""
    equity = {"return_3m": -0.05, "return_6m": -0.10, "volatility": 0.40}
    bond = {"spread_bps": 350.0, "spread_change_3m_bps": 40.0, "spread_percentile": 70.0}
    rating = {"rating_numeric": 10, "outlook": "NEGATIVE", "watch_status": None}

    signals = detect_divergence_signals(equity, bond, rating_data=rating)
    types = [s["signal_type"] for s in signals]
    assert "FALLEN_ANGEL_OVERHANG" in types


def test_signal_fallen_angel_watch_negative():
    """WATCH_NEGATIVE should trigger with higher severity."""
    equity = {"return_3m": -0.02, "return_6m": -0.05, "volatility": 0.35}
    bond = {"spread_bps": 300.0, "spread_change_3m_bps": 20.0, "spread_percentile": 60.0}
    rating = {"rating_numeric": 9, "outlook": "STABLE", "watch_status": "WATCH_NEGATIVE"}

    signals = detect_divergence_signals(equity, bond, rating_data=rating)
    sig = next(
        (s for s in signals if s["signal_type"] == "FALLEN_ANGEL_OVERHANG"),
        None,
    )
    assert sig is not None
    assert sig["severity"] == "HIGH"


def test_signal_cheap_bonds_cheap_equity():
    """Detect cheap bonds + cheap equity signal."""
    equity = {"return_3m": -0.10, "return_6m": -0.15, "pe_percentile": 15.0}
    bond = {"spread_bps": 400.0, "spread_change_3m_bps": 10.0, "spread_percentile": 85.0}

    signals = detect_divergence_signals(equity, bond)
    types = [s["signal_type"] for s in signals]
    assert "CHEAP_BONDS_CHEAP_EQUITY" in types


def test_signal_yield_curve_inversion():
    """Detect yield curve inversion + spread widening signal."""
    equity = {"return_3m": -0.02, "return_6m": -0.03}
    bond = {"spread_bps": 250.0, "spread_change_3m_bps": 50.0, "spread_percentile": 65.0}
    curve = {"slope_2s10s": -0.003, "is_inverted": True}

    signals = detect_divergence_signals(equity, bond, curve_data=curve)
    types = [s["signal_type"] for s in signals]
    assert "YIELD_CURVE_INVERSION_SIGNAL" in types


def test_no_signals_when_aligned():
    """No signals when equity and bonds are aligned (both healthy)."""
    equity = {"return_3m": 0.05, "return_6m": 0.10, "pe_percentile": 50.0, "volatility": 0.12}
    bond = {"spread_bps": 150.0, "spread_change_3m_bps": -10.0, "spread_percentile": 40.0}
    curve = {"slope_2s10s": 0.01, "is_inverted": False}

    signals = detect_divergence_signals(equity, bond, curve_data=curve)
    assert len(signals) == 0


def test_multiple_signals_can_fire_simultaneously():
    """Multiple signals can fire at once when conditions overlap."""
    equity = {"return_3m": 0.20, "return_6m": 0.25, "pe_percentile": 10.0, "volatility": 0.40}
    bond = {"spread_bps": 700.0, "spread_change_3m_bps": 250.0, "spread_percentile": 95.0}
    rating = {"rating_numeric": 10, "outlook": "NEGATIVE"}
    curve = {"slope_2s10s": -0.01, "is_inverted": True}

    signals = detect_divergence_signals(equity, bond, rating_data=rating, curve_data=curve)
    # Should have multiple signals
    assert len(signals) >= 3


def test_signal_structure_has_required_fields():
    """Every signal should have the required fields."""
    equity = {"return_3m": 0.20, "return_6m": 0.20}
    bond = {"spread_bps": 600.0, "spread_change_3m_bps": 100.0, "spread_percentile": 80.0}
    signals = detect_divergence_signals(equity, bond)
    for sig in signals:
        assert "signal_type" in sig
        assert "description" in sig
        assert "severity" in sig
        assert "actionability" in sig
        assert "confidence" in sig
        assert sig["signal_type"] in SIGNAL_TYPES


# ── Cross-Asset Regime Tests ─────────────────────────────────────────


def test_regime_risk_on():
    """RISK_ON: low vol, tight spreads, normal curve."""
    result = compute_cross_asset_regime(
        equity_vol=0.10,
        credit_spread=150.0,
        rate_level=0.03,
        curve_slope=0.015,
    )
    assert result["regime"] == "RISK_ON"
    assert result["confidence"] > 0.5
    assert result["factors"]["vol_signal"] == "RISK_ON"
    assert result["factors"]["credit_signal"] == "RISK_ON"


def test_regime_risk_off():
    """RISK_OFF: high vol, wide spreads, inverted curve."""
    result = compute_cross_asset_regime(
        equity_vol=0.30,
        credit_spread=450.0,
        rate_level=0.065,       # high rates → rate_score=2
        curve_slope=-0.01,
    )
    assert result["regime"] == "RISK_OFF"
    assert result["factors"]["vol_signal"] == "RISK_OFF"
    assert result["factors"]["credit_signal"] == "RISK_OFF"


def test_regime_stress():
    """STRESS: very high vol, very wide spreads."""
    result = compute_cross_asset_regime(
        equity_vol=0.40,
        credit_spread=700.0,
        rate_level=0.05,
        curve_slope=-0.02,
    )
    assert result["regime"] == "STRESS"
    assert result["confidence"] >= 0.80


def test_regime_transition():
    """TRANSITION: mixed signals."""
    result = compute_cross_asset_regime(
        equity_vol=0.18,
        credit_spread=250.0,
        rate_level=0.04,
        curve_slope=0.002,
    )
    assert result["regime"] == "TRANSITION"


# ── Equity Exposure Adjustment Tests ─────────────────────────────────


def test_exposure_reduce_in_stress():
    """STRESS regime should suggest reducing equity exposure."""
    result = compute_equity_exposure_adjustment(
        regime="STRESS",
        signals=[],
        current_equity_weight=0.60,
    )
    assert result["suggested_weight"] < 0.60
    assert result["adjustment_pct"] < 0
    assert result["confidence"] > 0.5


def test_exposure_maintain_in_risk_on():
    """RISK_ON regime should maintain or increase equity exposure."""
    result = compute_equity_exposure_adjustment(
        regime="RISK_ON",
        signals=[],
        current_equity_weight=0.60,
    )
    assert result["suggested_weight"] >= 0.60
    assert result["adjustment_pct"] >= 0


def test_exposure_signals_compound_with_regime():
    """Signals should compound with regime adjustments."""
    signals = [
        {"signal_type": "BOND_DISTRESS_BEFORE_EQUITY", "severity": "HIGH", "confidence": 0.85},
    ]
    result = compute_equity_exposure_adjustment(
        regime="RISK_OFF",
        signals=signals,
        current_equity_weight=0.60,
    )
    # Both regime and signal push to reduce
    assert result["suggested_weight"] < 0.50
    assert result["adjustment_pct"] < -0.10


def test_exposure_clamped_to_bounds():
    """Suggested weight should be clamped between 0.10 and 0.90."""
    signals = [
        {"signal_type": "BOND_DISTRESS_BEFORE_EQUITY", "severity": "HIGH", "confidence": 0.90},
        {"signal_type": "EQUITY_RALLY_BOND_DETERIORATION", "severity": "HIGH", "confidence": 0.85},
        {"signal_type": "FALLEN_ANGEL_OVERHANG", "severity": "HIGH", "confidence": 0.80},
        {"signal_type": "YIELD_CURVE_INVERSION_SIGNAL", "severity": "HIGH", "confidence": 0.75},
    ]
    result = compute_equity_exposure_adjustment(
        regime="STRESS",
        signals=signals,
        current_equity_weight=0.20,
    )
    assert result["suggested_weight"] >= 0.10
