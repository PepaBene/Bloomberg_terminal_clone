"""Tests for E2 WACC Extension — Market Cost of Debt (FI Supplement)."""

import pytest

from src.engines.e2_wacc import (
    compute_market_cost_of_debt,
    compute_wacc_with_market_debt_cost,
)


# ── Market Cost of Debt ────────────────────────────────────────────────


def test_market_cost_of_debt_basic():
    """Rf=4% + 200bps spread = 6% cost of debt."""
    result = compute_market_cost_of_debt(risk_free_rate=0.04, credit_spread_bps=200.0)
    assert result["cost_of_debt_market"] == pytest.approx(0.06, abs=1e-6)
    assert result["risk_free_rate"] == 0.04
    assert result["credit_spread_bps"] == 200.0


def test_market_cost_of_debt_zero_spread():
    """Zero spread means cost of debt = risk-free rate."""
    result = compute_market_cost_of_debt(risk_free_rate=0.035, credit_spread_bps=0.0)
    assert result["cost_of_debt_market"] == pytest.approx(0.035, abs=1e-6)


def test_market_cost_of_debt_wide_spread():
    """High-yield: Rf=4.5% + 600bps = 10.5%."""
    result = compute_market_cost_of_debt(risk_free_rate=0.045, credit_spread_bps=600.0)
    assert result["cost_of_debt_market"] == pytest.approx(0.105, abs=1e-6)


def test_market_cost_of_debt_low_rate_env():
    """Near-zero rate environment: Rf=0.5% + 150bps = 2.0%."""
    result = compute_market_cost_of_debt(risk_free_rate=0.005, credit_spread_bps=150.0)
    assert result["cost_of_debt_market"] == pytest.approx(0.02, abs=1e-6)


# ── WACC with Market Debt Cost ─────────────────────────────────────────


def test_wacc_market_basic():
    """Basic WACC with market debt cost."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10,
        cost_of_debt_market=0.06,
        equity_weight=0.60,
        debt_weight=0.40,
        tax_rate=0.21,
    )
    # WACC = 0.60 * 0.10 + 0.40 * 0.06 * (1-0.21) = 0.06 + 0.01896 = 0.07896
    assert result["wacc_market"] == pytest.approx(0.07896, abs=1e-5)
    assert result["cost_of_debt_market_pretax"] == 0.06
    assert result["cost_of_debt_market_aftertax"] == pytest.approx(0.06 * 0.79, abs=1e-6)


def test_wacc_market_all_equity():
    """100% equity company — WACC = cost of equity."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.12,
        cost_of_debt_market=0.05,
        equity_weight=1.0,
        debt_weight=0.0,
        tax_rate=0.21,
    )
    assert result["wacc_market"] == pytest.approx(0.12, abs=1e-6)


def test_wacc_market_high_leverage():
    """Highly leveraged: 80% debt."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.15,
        cost_of_debt_market=0.08,
        equity_weight=0.20,
        debt_weight=0.80,
        tax_rate=0.25,
    )
    # WACC = 0.20*0.15 + 0.80*0.08*0.75 = 0.03 + 0.048 = 0.078
    assert result["wacc_market"] == pytest.approx(0.078, abs=1e-5)


def test_wacc_market_zero_tax():
    """No tax shield."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10,
        cost_of_debt_market=0.06,
        equity_weight=0.50,
        debt_weight=0.50,
        tax_rate=0.0,
    )
    # WACC = 0.50*0.10 + 0.50*0.06*1.0 = 0.05 + 0.03 = 0.08
    assert result["wacc_market"] == pytest.approx(0.08, abs=1e-5)


def test_wacc_market_default_tax_rate():
    """Default tax rate should be 0.21 (US statutory)."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10,
        cost_of_debt_market=0.06,
        equity_weight=0.60,
        debt_weight=0.40,
    )
    # Should use 0.21 as default
    assert result["tax_rate"] == 0.21
    assert result["wacc_market"] == pytest.approx(
        0.60 * 0.10 + 0.40 * 0.06 * 0.79, abs=1e-5,
    )


def test_wacc_market_vs_implied_higher_spread():
    """Market cost of debt should be higher when credit spread is wider."""
    narrow = compute_market_cost_of_debt(0.04, 150.0)
    wide = compute_market_cost_of_debt(0.04, 500.0)
    assert wide["cost_of_debt_market"] > narrow["cost_of_debt_market"]

    wacc_narrow = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10, cost_of_debt_market=narrow["cost_of_debt_market"],
        equity_weight=0.60, debt_weight=0.40,
    )
    wacc_wide = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10, cost_of_debt_market=wide["cost_of_debt_market"],
        equity_weight=0.60, debt_weight=0.40,
    )
    assert wacc_wide["wacc_market"] > wacc_narrow["wacc_market"]


def test_wacc_market_result_fields():
    """Result should contain all expected fields."""
    result = compute_wacc_with_market_debt_cost(
        cost_of_equity=0.10, cost_of_debt_market=0.06,
        equity_weight=0.60, debt_weight=0.40,
    )
    expected_fields = {
        "wacc_market", "cost_of_equity", "cost_of_debt_market_pretax",
        "cost_of_debt_market_aftertax", "equity_weight", "debt_weight", "tax_rate",
    }
    assert set(result.keys()) == expected_fields
