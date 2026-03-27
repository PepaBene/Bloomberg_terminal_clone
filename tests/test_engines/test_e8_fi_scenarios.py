"""Tests for E8 FI Extension: Fixed Income Scenario & Sensitivity Analysis."""

import pytest

from src.engines.e8_fi_scenarios import (
    fi_scenario_shift,
    fi_sensitivity_table,
)


# ---------------------------------------------------------------------------
# Sample position helpers
# ---------------------------------------------------------------------------


def _bond_position(
    mv: float = 1_000_000,
    dur: float = 5.0,
    cvx: float = 30.0,
    spread_dur: float | None = None,
    rating: int | None = None,
    cusip: str = "TEST001",
) -> dict:
    return {
        "cusip": cusip,
        "market_value": mv,
        "modified_duration": dur,
        "convexity": cvx,
        "spread_duration": spread_dur,
        "rating_numeric": rating,
    }


# ===========================================================================
# 1D Sensitivity Table
# ===========================================================================


def test_sensitivity_1d_structure():
    """1D table should have correct structure and field names."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[-100, -50, 0, 50, 100],
    )
    assert result["var1_name"] == "yield_shift_bps"
    assert result["var2_name"] is None
    assert len(result["results"]) == 5


def test_sensitivity_1d_zero_shift_returns_base_price():
    """A 0bps shift should return the base price."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[0.0],
    )
    cell = result["results"][0]
    assert cell["price"] == pytest.approx(100.0, abs=0.01)
    assert cell["price_change_pct"] == pytest.approx(0.0, abs=0.01)


def test_sensitivity_1d_rate_up_price_down():
    """Positive yield shift should decrease price."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[100],
    )
    cell = result["results"][0]
    # ΔP/P = -5 * 0.01 + 0.5 * 30 * 0.01² = -0.05 + 0.0015 = -0.0485
    # new price = 100 * (1 - 0.0485) = 95.15
    assert cell["price"] == pytest.approx(95.15, abs=0.01)


def test_sensitivity_1d_rate_down_price_up():
    """Negative yield shift should increase price."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[-100],
    )
    cell = result["results"][0]
    # ΔP/P = -5 * (-0.01) + 0.5 * 30 * (-0.01)² = 0.05 + 0.0015 = 0.0515
    assert cell["price"] == pytest.approx(105.15, abs=0.01)


def test_sensitivity_1d_convexity_benefit():
    """Bond with convexity gains more when rates fall than it loses when rates rise."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=50.0,
        var1_name="yield_shift_bps",
        var1_range=[-100, 100],
    )
    down_cell = result["results"][0]  # -100bps
    up_cell = result["results"][1]    # +100bps

    gain = down_cell["price"] - 100.0
    loss = 100.0 - up_cell["price"]
    assert gain > loss  # convexity benefit


# ===========================================================================
# 2D Sensitivity Table (yield x spread)
# ===========================================================================


def test_sensitivity_2d_structure():
    """2D table should have var1 x var2 entries."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[-50, 0, 50],
        var2_name="spread_shift_bps",
        var2_range=[-25, 0, 25],
    )
    assert result["var1_name"] == "yield_shift_bps"
    assert result["var2_name"] == "spread_shift_bps"
    assert len(result["results"]) == 9  # 3 x 3


def test_sensitivity_2d_both_zero():
    """Both shifts at zero should return the base price."""
    result = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[0],
        var2_name="spread_shift_bps",
        var2_range=[0],
    )
    cell = result["results"][0]
    assert cell["price"] == pytest.approx(100.0, abs=0.01)


def test_sensitivity_2d_additive():
    """Combined shift should equal sum of individual shifts in the model."""
    # yield +50 + spread +50 = total +100bps
    result_2d = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[50],
        var2_name="spread_shift_bps",
        var2_range=[50],
    )
    result_1d = fi_sensitivity_table(
        base_price=100.0,
        modified_duration=5.0,
        convexity=30.0,
        var1_name="yield_shift_bps",
        var1_range=[100],
    )
    assert result_2d["results"][0]["price"] == pytest.approx(
        result_1d["results"][0]["price"], abs=0.01
    )


# ===========================================================================
# Multi-variable scenario shift
# ===========================================================================


def test_scenario_shift_yield_only():
    """Pure yield shift, no spread or migration."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=30.0)
    result = fi_scenario_shift([pos], yield_shift_bps=100)

    # ΔP = 1M * (-5*0.01 + 0.5*30*0.01²) = 1M * (-0.0485) = -48,500
    assert result["yield_impact"] == pytest.approx(-48_500.0, abs=1.0)
    assert result["spread_impact"] == 0.0
    assert result["migration_impact"] == 0.0
    assert result["total_pnl"] == pytest.approx(-48_500.0, abs=1.0)


def test_scenario_shift_spread_only():
    """Pure spread widening, no yield shift."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=30.0, spread_dur=5.0)
    result = fi_scenario_shift([pos], spread_shift_bps=50)

    # Spread P&L = 1M * (-5.0 * 0.005) = -25,000
    assert result["spread_impact"] == pytest.approx(-25_000.0, abs=1.0)
    assert result["yield_impact"] == 0.0


def test_scenario_shift_combined():
    """Combined yield + spread shift."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=30.0, spread_dur=4.0)
    result = fi_scenario_shift([pos], yield_shift_bps=100, spread_shift_bps=50)

    # Yield: 1M * (-5*0.01 + 0.5*30*0.01²) = -48,500
    # Spread: 1M * (-4.0 * 0.005) = -20,000
    assert result["yield_impact"] == pytest.approx(-48_500.0, abs=1.0)
    assert result["spread_impact"] == pytest.approx(-20_000.0, abs=1.0)
    assert result["total_pnl"] == pytest.approx(-68_500.0, abs=1.0)


# ===========================================================================
# Rating migration impact
# ===========================================================================


def test_rating_migration_downgrade():
    """Downgrade (positive notches) should cause loss via spread widening."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=0.0, spread_dur=5.0)
    result = fi_scenario_shift([pos], rating_migration_notches=2)

    # Migration: 2 notches * 25bps = 50bps = 0.005 decimal
    # P&L = 1M * (-5.0 * 0.005) = -25,000
    assert result["migration_impact"] == pytest.approx(-25_000.0, abs=1.0)
    assert result["total_pnl"] == pytest.approx(-25_000.0, abs=1.0)


def test_rating_migration_upgrade():
    """Upgrade (negative notches) should produce a gain."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=0.0, spread_dur=5.0)
    result = fi_scenario_shift([pos], rating_migration_notches=-2)

    # Migration: -2 notches * 25bps = -50bps = -0.005 decimal
    # P&L = 1M * (-5.0 * -0.005) = +25,000
    assert result["migration_impact"] == pytest.approx(25_000.0, abs=1.0)
    assert result["total_pnl"] > 0


def test_scenario_shift_portfolio_aggregation():
    """Multi-position portfolio aggregates correctly."""
    pos1 = _bond_position(mv=1_000_000, dur=5.0, cvx=30.0, spread_dur=5.0, cusip="A")
    pos2 = _bond_position(mv=2_000_000, dur=3.0, cvx=10.0, spread_dur=3.0, cusip="B")
    result = fi_scenario_shift(
        [pos1, pos2],
        yield_shift_bps=50,
        spread_shift_bps=25,
        rating_migration_notches=1,
    )
    assert result["position_count"] == 2
    assert len(result["by_position"]) == 2

    # Total should be sum of individual
    total_from_positions = sum(p["total_pnl"] for p in result["by_position"])
    assert result["total_pnl"] == pytest.approx(total_from_positions, abs=0.01)

    # Pct based on 3M total MV
    expected_pct = result["total_pnl"] / 3_000_000 * 100
    assert result["total_pnl_pct"] == pytest.approx(expected_pct, abs=0.01)


def test_scenario_shift_no_shifts():
    """Zero shifts across all variables -> zero P&L."""
    pos = _bond_position(mv=1_000_000, dur=5.0, cvx=30.0)
    result = fi_scenario_shift([pos])
    assert result["total_pnl"] == 0.0
    assert result["yield_impact"] == 0.0
    assert result["spread_impact"] == 0.0
    assert result["migration_impact"] == 0.0
