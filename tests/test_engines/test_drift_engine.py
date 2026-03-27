"""Tests for Pillar 4 Phase 3 — Drift Engine."""

from __future__ import annotations

import math

import pytest

from src.engines.drift_engine import (
    DRIFT_THRESHOLDS,
    REBALANCE_THRESHOLD,
    DriftAlert,
    DriftResult,
    PositionDrift,
    SectorDrift,
    analyze_drift,
    classify_drift,
    compute_position_drift,
    compute_sector_drift,
    compute_total_drift,
    compute_tracking_error,
    generate_drift_alerts,
    suggest_rebalance_trades,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def target_weights():
    return {"AAPL": 20.0, "MSFT": 20.0, "JPM": 20.0, "JNJ": 20.0, "XOM": 20.0}


@pytest.fixture
def current_weights_low_drift():
    return {"AAPL": 21.0, "MSFT": 19.5, "JPM": 20.5, "JNJ": 19.5, "XOM": 19.5}


@pytest.fixture
def current_weights_high_drift():
    return {"AAPL": 30.0, "MSFT": 25.0, "JPM": 20.0, "JNJ": 15.0, "XOM": 10.0}


@pytest.fixture
def positions_with_sectors():
    return [
        {"ticker": "AAPL", "weight": 30.0, "sector": "Technology"},
        {"ticker": "MSFT", "weight": 25.0, "sector": "Technology"},
        {"ticker": "JPM", "weight": 20.0, "sector": "Financials"},
        {"ticker": "JNJ", "weight": 15.0, "sector": "Healthcare"},
        {"ticker": "XOM", "weight": 10.0, "sector": "Energy"},
    ]


@pytest.fixture
def target_sector_weights():
    return {"Technology": 40.0, "Financials": 25.0, "Healthcare": 20.0, "Energy": 15.0}


# ── Constants Tests ──────────────────────────────────────────────────────


class TestConstants:
    def test_drift_thresholds_keys(self):
        assert set(DRIFT_THRESHOLDS.keys()) == {"MINIMAL", "MODERATE", "SIGNIFICANT"}

    def test_drift_thresholds_values(self):
        assert DRIFT_THRESHOLDS["MINIMAL"] == 2.0
        assert DRIFT_THRESHOLDS["MODERATE"] == 5.0
        assert DRIFT_THRESHOLDS["SIGNIFICANT"] == 10.0

    def test_rebalance_threshold(self):
        assert REBALANCE_THRESHOLD == 5.0


# ── compute_position_drift Tests ─────────────────────────────────────────


class TestComputePositionDrift:
    def test_basic_drift(self, target_weights, current_weights_high_drift):
        drifts = compute_position_drift(current_weights_high_drift, target_weights)
        assert len(drifts) == 5
        # Sorted by abs_drift descending
        assert drifts[0].abs_drift >= drifts[-1].abs_drift

    def test_drift_values(self, target_weights, current_weights_high_drift):
        drifts = compute_position_drift(current_weights_high_drift, target_weights)
        aapl = next(d for d in drifts if d.ticker == "AAPL")
        assert aapl.drift_pct == 10.0
        assert aapl.action_needed == "SELL"

    def test_buy_action(self, target_weights, current_weights_high_drift):
        drifts = compute_position_drift(current_weights_high_drift, target_weights)
        xom = next(d for d in drifts if d.ticker == "XOM")
        assert xom.drift_pct == -10.0
        assert xom.action_needed == "BUY"

    def test_hold_action(self, target_weights):
        current = {"AAPL": 20.0, "MSFT": 20.0, "JPM": 20.0, "JNJ": 20.0, "XOM": 20.0}
        drifts = compute_position_drift(current, target_weights)
        for d in drifts:
            assert d.action_needed == "HOLD"

    def test_new_position_in_target(self):
        current = {"AAPL": 50.0, "MSFT": 50.0}
        target = {"AAPL": 40.0, "MSFT": 40.0, "GOOG": 20.0}
        drifts = compute_position_drift(current, target)
        goog = next(d for d in drifts if d.ticker == "GOOG")
        assert goog.current_weight == 0.0
        assert goog.target_weight == 20.0
        assert goog.action_needed == "BUY"

    def test_removed_position(self):
        current = {"AAPL": 50.0, "MSFT": 30.0, "GOOG": 20.0}
        target = {"AAPL": 50.0, "MSFT": 50.0}
        drifts = compute_position_drift(current, target)
        goog = next(d for d in drifts if d.ticker == "GOOG")
        assert goog.action_needed == "SELL"

    def test_empty_weights(self):
        drifts = compute_position_drift({}, {})
        assert drifts == []


# ── compute_sector_drift Tests ───────────────────────────────────────────


class TestComputeSectorDrift:
    def test_basic_sector_drift(self, positions_with_sectors, target_sector_weights):
        drifts = compute_sector_drift(positions_with_sectors, target_sector_weights)
        assert len(drifts) == 4

    def test_tech_overweight(self, positions_with_sectors, target_sector_weights):
        drifts = compute_sector_drift(positions_with_sectors, target_sector_weights)
        tech = next(d for d in drifts if d.sector == "Technology")
        # Current: 30+25=55, target: 40 => drift = 15
        assert tech.drift_pct == 15.0

    def test_energy_underweight(self, positions_with_sectors, target_sector_weights):
        drifts = compute_sector_drift(positions_with_sectors, target_sector_weights)
        energy = next(d for d in drifts if d.sector == "Energy")
        assert energy.drift_pct == -5.0

    def test_sorted_by_abs_drift(self, positions_with_sectors, target_sector_weights):
        drifts = compute_sector_drift(positions_with_sectors, target_sector_weights)
        abs_drifts = [abs(d.drift_pct) for d in drifts]
        assert abs_drifts == sorted(abs_drifts, reverse=True)

    def test_empty_positions(self, target_sector_weights):
        drifts = compute_sector_drift([], target_sector_weights)
        for d in drifts:
            assert d.current_weight == 0.0


# ── compute_total_drift Tests ────────────────────────────────────────────


class TestComputeTotalDrift:
    def test_basic(self):
        drifts = [
            PositionDrift("A", 50.0, 60.0, 10.0, 10.0, "SELL"),
            PositionDrift("B", 50.0, 40.0, -10.0, 10.0, "BUY"),
        ]
        assert compute_total_drift(drifts) == 10.0

    def test_zero_drift(self):
        drifts = [
            PositionDrift("A", 50.0, 50.0, 0.0, 0.0, "HOLD"),
            PositionDrift("B", 50.0, 50.0, 0.0, 0.0, "HOLD"),
        ]
        assert compute_total_drift(drifts) == 0.0

    def test_empty_list(self):
        assert compute_total_drift([]) == 0.0


# ── classify_drift Tests ────────────────────────────────────────────────


class TestClassifyDrift:
    def test_minimal(self):
        assert classify_drift(1.0) == "MINIMAL"
        assert classify_drift(2.0) == "MINIMAL"

    def test_moderate(self):
        assert classify_drift(3.0) == "MODERATE"
        assert classify_drift(5.0) == "MODERATE"

    def test_significant(self):
        assert classify_drift(7.0) == "SIGNIFICANT"
        assert classify_drift(10.0) == "SIGNIFICANT"

    def test_critical(self):
        assert classify_drift(15.0) == "CRITICAL"
        assert classify_drift(50.0) == "CRITICAL"

    def test_zero(self):
        assert classify_drift(0.0) == "MINIMAL"


# ── suggest_rebalance_trades Tests ───────────────────────────────────────


class TestSuggestRebalanceTrades:
    def test_basic_trades(self):
        drifts = [
            PositionDrift("A", 50.0, 60.0, 10.0, 10.0, "SELL"),
            PositionDrift("B", 50.0, 40.0, -10.0, 10.0, "BUY"),
        ]
        trades = suggest_rebalance_trades(drifts, 1_000_000)
        assert len(trades) == 2
        sell = next(t for t in trades if t["ticker"] == "A")
        assert sell["action"] == "SELL"
        assert sell["notional_amount"] == 100_000.0

    def test_no_trades_for_hold(self):
        drifts = [
            PositionDrift("A", 50.0, 50.0, 0.0, 0.0, "HOLD"),
        ]
        trades = suggest_rebalance_trades(drifts, 1_000_000)
        assert len(trades) == 0

    def test_zero_nav(self):
        drifts = [
            PositionDrift("A", 50.0, 60.0, 10.0, 10.0, "SELL"),
        ]
        trades = suggest_rebalance_trades(drifts, 0.0)
        assert trades == []

    def test_sorted_by_notional(self):
        drifts = [
            PositionDrift("A", 50.0, 55.0, 5.0, 5.0, "SELL"),
            PositionDrift("B", 50.0, 40.0, -10.0, 10.0, "BUY"),
        ]
        trades = suggest_rebalance_trades(drifts, 1_000_000)
        assert trades[0]["notional_amount"] >= trades[1]["notional_amount"]


# ── generate_drift_alerts Tests ──────────────────────────────────────────


class TestGenerateDriftAlerts:
    def _make_drift_result(self, total=0.0, classification="MINIMAL",
                           rebalance=False, position_drifts=None,
                           rebalance_trades=None):
        return DriftResult(
            total_drift_pct=total,
            max_position_drift_pct=0.0,
            max_sector_drift_pct=0.0,
            classification=classification,
            rebalance_needed=rebalance,
            position_drifts=position_drifts or [],
            sector_drifts=[],
            rebalance_trades=rebalance_trades or [],
        )

    def test_significant_drift_alert(self):
        dr = self._make_drift_result(total=12.0, classification="CRITICAL")
        alerts = generate_drift_alerts(dr)
        types = [a.alert_type for a in alerts]
        assert "DRIFT_THRESHOLD" in types

    def test_rebalance_alert(self):
        dr = self._make_drift_result(total=6.0, classification="MODERATE",
                                     rebalance=True, rebalance_trades=[{}])
        alerts = generate_drift_alerts(dr)
        types = [a.alert_type for a in alerts]
        assert "REBALANCE_NEEDED" in types

    def test_position_drift_alert(self):
        pd = PositionDrift("AAPL", 20.0, 35.0, 15.0, 15.0, "SELL")
        dr = self._make_drift_result(total=8.0, classification="SIGNIFICANT",
                                     position_drifts=[pd])
        alerts = generate_drift_alerts(dr)
        types = [a.alert_type for a in alerts]
        assert "POSITION_DRIFT" in types

    def test_worsening_drift_alert(self):
        prior = self._make_drift_result(total=3.0, classification="MODERATE")
        current = self._make_drift_result(total=6.0, classification="MODERATE")
        alerts = generate_drift_alerts(current, prior)
        types = [a.alert_type for a in alerts]
        assert "DRIFT_WORSENING" in types

    def test_no_alert_minimal(self):
        dr = self._make_drift_result(total=1.0, classification="MINIMAL")
        alerts = generate_drift_alerts(dr)
        assert len(alerts) == 0

    def test_no_worsening_when_minimal(self):
        prior = self._make_drift_result(total=0.5, classification="MINIMAL")
        current = self._make_drift_result(total=1.5, classification="MINIMAL")
        alerts = generate_drift_alerts(current, prior)
        types = [a.alert_type for a in alerts]
        assert "DRIFT_WORSENING" not in types


# ── analyze_drift Tests ──────────────────────────────────────────────────


class TestAnalyzeDrift:
    def test_basic_analysis(self, target_weights, current_weights_high_drift):
        result = analyze_drift(current_weights_high_drift, target_weights)
        assert result.total_drift_pct > 0
        assert result.classification in ("MINIMAL", "MODERATE", "SIGNIFICANT", "CRITICAL")
        assert len(result.position_drifts) == 5

    def test_low_drift_no_rebalance(self, target_weights, current_weights_low_drift):
        result = analyze_drift(current_weights_low_drift, target_weights)
        assert result.rebalance_needed is False
        assert result.classification == "MINIMAL"

    def test_high_drift_needs_rebalance(self, target_weights, current_weights_high_drift):
        result = analyze_drift(
            current_weights_high_drift, target_weights, portfolio_nav=1_000_000,
        )
        assert result.rebalance_needed is True
        assert len(result.rebalance_trades) > 0

    def test_sector_drift_included(
        self, target_weights, current_weights_high_drift,
        positions_with_sectors, target_sector_weights,
    ):
        result = analyze_drift(
            current_weights_high_drift,
            target_weights,
            positions=positions_with_sectors,
            target_sector_weights=target_sector_weights,
        )
        assert len(result.sector_drifts) > 0
        assert result.max_sector_drift_pct > 0

    def test_no_sector_drift_without_data(self, target_weights, current_weights_high_drift):
        result = analyze_drift(current_weights_high_drift, target_weights)
        assert result.sector_drifts == []
        assert result.max_sector_drift_pct == 0.0

    def test_perfect_weights(self, target_weights):
        result = analyze_drift(dict(target_weights), target_weights)
        assert result.total_drift_pct == 0.0
        assert result.classification == "MINIMAL"
        assert result.rebalance_needed is False


# ── compute_tracking_error Tests ─────────────────────────────────────────


class TestComputeTrackingError:
    def test_identical_returns(self):
        returns = [0.01, -0.005, 0.003, 0.002, -0.001]
        te = compute_tracking_error(returns, returns)
        assert te == 0.0

    def test_different_returns(self):
        portfolio = [0.01, -0.005, 0.003, 0.002, -0.001]
        benchmark = [0.008, -0.003, 0.001, 0.004, -0.002]
        te = compute_tracking_error(portfolio, benchmark)
        assert te > 0

    def test_annualized(self):
        # Manual check: tracking error should be scaled by sqrt(252)
        portfolio = [0.01, 0.02]
        benchmark = [0.005, 0.01]
        diffs = [0.005, 0.01]
        mean_diff = 0.0075
        var = ((0.005 - 0.0075) ** 2 + (0.01 - 0.0075) ** 2) / 1
        expected = math.sqrt(var) * math.sqrt(252)
        te = compute_tracking_error(portfolio, benchmark)
        assert abs(te - round(expected, 6)) < 1e-4

    def test_insufficient_data(self):
        assert compute_tracking_error([0.01], [0.01]) == 0.0
        assert compute_tracking_error([], []) == 0.0

    def test_different_lengths(self):
        portfolio = [0.01, 0.02, 0.03]
        benchmark = [0.005, 0.01]
        te = compute_tracking_error(portfolio, benchmark)
        # Should use min(len) = 2
        assert te > 0
