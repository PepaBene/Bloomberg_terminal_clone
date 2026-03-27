"""Tests for E5 FI Extension: Fixed Income Rate Shock Scenarios."""

import pytest

from src.engines.e5_fi_rate_shocks import (
    FI_RATE_SCENARIOS,
    apply_fi_rate_scenario,
    get_fi_rate_scenario,
    get_fi_rate_scenarios,
)


# ---------------------------------------------------------------------------
# Helper: build portfolio positions
# ---------------------------------------------------------------------------


def _ig_position(mv: float = 1_000_000, dur: float = 5.0, cvx: float = 30.0) -> dict:
    """An investment-grade bond position."""
    return {
        "cusip": "IG_BOND_01",
        "market_value": mv,
        "modified_duration": dur,
        "convexity": cvx,
        "spread_duration": dur,
        "is_investment_grade": True,
    }


def _hy_position(mv: float = 1_000_000, dur: float = 4.0, cvx: float = 20.0) -> dict:
    """A high-yield bond position."""
    return {
        "cusip": "HY_BOND_01",
        "market_value": mv,
        "modified_duration": dur,
        "convexity": cvx,
        "spread_duration": dur,
        "is_investment_grade": False,
    }


# ---------------------------------------------------------------------------
# Scenario catalogue
# ---------------------------------------------------------------------------


def test_get_all_scenarios_returns_four():
    """There should be exactly four pre-defined scenarios."""
    scenarios = get_fi_rate_scenarios()
    assert len(scenarios) == 4


def test_get_single_scenario():
    """Look up a single scenario by ID."""
    s = get_fi_rate_scenario("BOND_MASSACRE_1994")
    assert s is not None
    assert s["rate_shift_bps"] == 300


def test_unknown_scenario_raises():
    """Applying an unknown scenario should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown FI rate scenario"):
        apply_fi_rate_scenario([_ig_position()], "NONEXISTENT")


# ---------------------------------------------------------------------------
# 1994 Bond Massacre
# ---------------------------------------------------------------------------


def test_bond_massacre_1994_ig():
    """1994 scenario on an IG bond: expect significant loss from 300bps rate rise."""
    pos = _ig_position(mv=1_000_000, dur=5.0, cvx=30.0)
    result = apply_fi_rate_scenario([pos], "BOND_MASSACRE_1994")

    assert result["total_pnl"] < 0  # rates up -> loss
    assert result["rate_pnl"] < 0
    assert result["spread_pnl"] < 0  # spreads widen -> additional loss

    # Rate P&L = 1M * (-5.0 * 0.03 + 0.5 * 30 * 0.03²) = 1M * (-0.15 + 0.0135) = -136,500
    assert result["rate_pnl"] == pytest.approx(-136_500.0, abs=1.0)

    # Spread P&L (IG) = 1M * (-5.0 * 50/10000) = 1M * (-5.0 * 0.005) = -25,000
    assert result["spread_pnl"] == pytest.approx(-25_000.0, abs=1.0)


# ---------------------------------------------------------------------------
# 2013 Taper Tantrum
# ---------------------------------------------------------------------------


def test_taper_tantrum_2013():
    """2013 Taper Tantrum: moderate rate rise (140bps)."""
    pos = _ig_position(mv=1_000_000, dur=7.0, cvx=60.0)
    result = apply_fi_rate_scenario([pos], "TAPER_TANTRUM_2013")

    # Rate P&L = 1M * (-7.0 * 0.014 + 0.5 * 60 * 0.014²)
    #          = 1M * (-0.098 + 0.00588) = -92,120
    assert result["rate_pnl"] == pytest.approx(-92_120.0, abs=1.0)
    assert result["total_pnl"] < 0


# ---------------------------------------------------------------------------
# 2022 Fed Hiking Cycle
# ---------------------------------------------------------------------------


def test_rate_shock_2022_hy():
    """2022 scenario on an HY bond: spread impact should be large."""
    pos = _hy_position(mv=1_000_000, dur=4.0, cvx=20.0)
    result = apply_fi_rate_scenario([pos], "RATE_SHOCK_2022")

    # Rate P&L = 1M * (-4.0 * 0.0425 + 0.5 * 20 * 0.0425²)
    #          = 1M * (-0.17 + 0.018063) = -151,937.5
    assert result["rate_pnl"] == pytest.approx(-151_937.5, abs=1.0)

    # Spread P&L (HY) = 1M * (-4.0 * 0.025) = -100,000
    assert result["spread_pnl"] == pytest.approx(-100_000.0, abs=1.0)


# ---------------------------------------------------------------------------
# 2019 Bull Rally (rates DOWN)
# ---------------------------------------------------------------------------


def test_bull_rally_2019_positive_pnl():
    """2019 rally: rates fall -> positive P&L."""
    pos = _ig_position(mv=1_000_000, dur=5.0, cvx=30.0)
    result = apply_fi_rate_scenario([pos], "BULL_RALLY_2019")

    assert result["total_pnl"] > 0  # rates down + spreads compress -> gain
    assert result["rate_pnl"] > 0
    assert result["spread_pnl"] > 0


# ---------------------------------------------------------------------------
# IG vs HY differential spread impact
# ---------------------------------------------------------------------------


def test_ig_vs_hy_spread_differential():
    """HY bonds should experience wider spread impact than IG for the same scenario."""
    ig = _ig_position(mv=1_000_000, dur=5.0, cvx=0.0)
    hy = _hy_position(mv=1_000_000, dur=5.0, cvx=0.0)
    # Use same duration/convexity so only spread differs
    hy["spread_duration"] = 5.0

    ig_result = apply_fi_rate_scenario([ig], "BOND_MASSACRE_1994")
    hy_result = apply_fi_rate_scenario([hy], "BOND_MASSACRE_1994")

    # Rate P&L should be the same (same dur/cvx)
    assert ig_result["rate_pnl"] == pytest.approx(hy_result["rate_pnl"], abs=1.0)

    # HY spread loss should be worse (150bps vs 50bps)
    assert abs(hy_result["spread_pnl"]) > abs(ig_result["spread_pnl"])
    # Specifically, HY spread = 3x IG spread for 1994
    assert hy_result["spread_pnl"] == pytest.approx(ig_result["spread_pnl"] * 3, abs=1.0)


# ---------------------------------------------------------------------------
# Mixed IG/HY portfolio
# ---------------------------------------------------------------------------


def test_mixed_portfolio():
    """Portfolio with both IG and HY positions aggregates correctly."""
    ig = _ig_position(mv=1_000_000, dur=5.0, cvx=30.0)
    hy = _hy_position(mv=500_000, dur=4.0, cvx=20.0)
    result = apply_fi_rate_scenario([ig, hy], "BOND_MASSACRE_1994")

    # Check by_position has 2 entries
    assert len(result["by_position"]) == 2
    assert result["by_position"][0]["cusip"] == "IG_BOND_01"
    assert result["by_position"][1]["cusip"] == "HY_BOND_01"

    # Total P&L = sum of individual P&Ls
    sum_pnl = sum(p["total_pnl"] for p in result["by_position"])
    assert result["total_pnl"] == pytest.approx(sum_pnl, abs=0.01)

    # total_pnl_pct is based on combined MV (1.5M)
    expected_pct = result["total_pnl"] / 1_500_000 * 100
    assert result["total_pnl_pct"] == pytest.approx(expected_pct, abs=0.01)


# ---------------------------------------------------------------------------
# Edge: zero-duration bond is immune to rate changes
# ---------------------------------------------------------------------------


def test_zero_duration_immune_to_rates():
    """A zero-duration bond should have zero rate P&L."""
    pos = {
        "cusip": "CASH",
        "market_value": 1_000_000,
        "modified_duration": 0.0,
        "convexity": 0.0,
        "spread_duration": 0.0,
        "is_investment_grade": True,
    }
    result = apply_fi_rate_scenario([pos], "RATE_SHOCK_2022")
    assert result["rate_pnl"] == 0.0
    assert result["spread_pnl"] == 0.0
    assert result["total_pnl"] == 0.0
