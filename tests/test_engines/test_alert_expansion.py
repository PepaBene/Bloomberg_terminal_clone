"""Tests for Pillar 3 Phase 3C — Part 17: Alert Expansion Engine."""

import pytest

from src.engines.alert_expansion import (
    FI_ALERT_TYPES,
    FLOW_ALERT_TYPES,
    QUALITY_ALERT_TYPES,
    check_curve_inversion,
    check_distress_threshold,
    check_fallen_angel,
    check_rating_change,
    check_regime_change,
    check_score_change,
    check_spread_widening,
    evaluate_fi_alerts,
    evaluate_flow_alerts,
    evaluate_quality_alerts,
    prioritize_alerts,
)


# ── Constants ─────────────────────────────────────────────────────────────


class TestConstants:
    def test_fi_alert_types_count(self):
        assert len(FI_ALERT_TYPES) == 13

    def test_quality_alert_types_count(self):
        assert len(QUALITY_ALERT_TYPES) == 5

    def test_flow_alert_types_count(self):
        assert len(FLOW_ALERT_TYPES) == 6

    def test_fi_alert_types_have_severity(self):
        for key, val in FI_ALERT_TYPES.items():
            assert "severity" in val, f"{key} missing severity"
            assert "description" in val, f"{key} missing description"


# ── check_rating_change ───────────────────────────────────────────────────


class TestCheckRatingChange:
    def test_no_change(self):
        assert check_rating_change("BBB", "BBB") is None

    def test_upgrade(self):
        result = check_rating_change("A", "BBB+")
        assert result is not None
        assert result["alert_type"] == "RATING_UPGRADE"

    def test_downgrade(self):
        result = check_rating_change("BBB", "A-")
        assert result is not None
        assert result["alert_type"] == "RATING_DOWNGRADE"

    def test_fallen_angel(self):
        result = check_rating_change("BB+", "BBB-")
        assert result is not None
        assert result["alert_type"] == "FALLEN_ANGEL"
        assert result["severity"] == "CRITICAL"

    def test_rising_star(self):
        result = check_rating_change("BBB-", "BB+")
        assert result is not None
        assert result["alert_type"] == "RISING_STAR"
        assert result["severity"] == "HIGH"

    def test_invalid_rating(self):
        assert check_rating_change("BBB", "INVALID") is None

    def test_both_invalid(self):
        assert check_rating_change("XYZ", "ABC") is None


# ── check_fallen_angel ────────────────────────────────────────────────────


class TestCheckFallenAngel:
    def test_fallen_angel_risk(self):
        result = check_fallen_angel("BBB-", "DETERIORATING")
        assert result is not None
        assert result["alert_type"] == "FALLEN_ANGEL"
        assert result["severity"] == "CRITICAL"

    def test_no_risk_stable(self):
        assert check_fallen_angel("BBB-", "STABLE") is None

    def test_no_risk_other_rating(self):
        assert check_fallen_angel("BBB", "DETERIORATING") is None

    def test_no_risk_hy(self):
        assert check_fallen_angel("BB+", "DETERIORATING") is None


# ── check_spread_widening ─────────────────────────────────────────────────


class TestCheckSpreadWidening:
    def test_widening(self):
        result = check_spread_widening(30.0)
        assert result is not None
        assert result["alert_type"] == "SPREAD_WIDENING"
        assert result["severity"] == "MEDIUM"

    def test_large_widening(self):
        result = check_spread_widening(60.0)
        assert result is not None
        assert result["severity"] == "HIGH"

    def test_no_widening(self):
        assert check_spread_widening(15.0) is None

    def test_custom_threshold(self):
        result = check_spread_widening(15.0, threshold=10.0)
        assert result is not None


# ── check_distress_threshold ──────────────────────────────────────────────


class TestCheckDistressThreshold:
    def test_distress(self):
        result = check_distress_threshold(600.0)
        assert result is not None
        assert result["alert_type"] == "DISTRESS_THRESHOLD"
        assert result["severity"] == "CRITICAL"

    def test_no_distress(self):
        assert check_distress_threshold(400.0) is None

    def test_custom_threshold(self):
        result = check_distress_threshold(400.0, threshold=300.0)
        assert result is not None


# ── check_curve_inversion ─────────────────────────────────────────────────


class TestCheckCurveInversion:
    def test_inversion(self):
        result = check_curve_inversion(-10.0, 5.0)
        assert result is not None
        assert result["alert_type"] == "CURVE_INVERSION"
        assert result["severity"] == "HIGH"

    def test_uninversion(self):
        result = check_curve_inversion(5.0, -10.0)
        assert result is not None
        assert result["alert_type"] == "CURVE_STEEPENING"
        assert result["severity"] == "MEDIUM"

    def test_no_crossing(self):
        assert check_curve_inversion(10.0, 20.0) is None

    def test_no_crossing_both_negative(self):
        assert check_curve_inversion(-10.0, -5.0) is None


# ── check_regime_change ───────────────────────────────────────────────────


class TestCheckRegimeChange:
    def test_no_change(self):
        assert check_regime_change("NORMAL", "NORMAL") is None

    def test_to_stress(self):
        result = check_regime_change("STRESS", "RISK_OFF")
        assert result is not None
        assert result["severity"] == "CRITICAL"

    def test_to_risk_off(self):
        result = check_regime_change("RISK_OFF", "NORMAL")
        assert result is not None
        assert result["severity"] == "HIGH"

    def test_to_risk_on(self):
        result = check_regime_change("RISK_ON", "NORMAL")
        assert result is not None
        assert result["severity"] == "LOW"


# ── evaluate_fi_alerts ────────────────────────────────────────────────────


class TestEvaluateFIAlerts:
    def test_comprehensive(self):
        data = {
            "current_rating": "BB+",
            "prior_rating": "BBB-",
            "momentum": "DETERIORATING",
            "spread_change_bps": 35.0,
            "spread_bps": 550.0,
            "spread_2s10s": -5.0,
            "prior_2s10s": 10.0,
            "current_regime": "STRESS",
            "prior_regime": "RISK_OFF",
        }
        alerts = evaluate_fi_alerts(data)
        alert_types = {a["alert_type"] for a in alerts}
        assert "FALLEN_ANGEL" in alert_types
        assert "SPREAD_WIDENING" in alert_types
        assert "DISTRESS_THRESHOLD" in alert_types
        assert "CURVE_INVERSION" in alert_types
        assert "REGIME_CHANGE" in alert_types

    def test_no_alerts(self):
        data = {
            "current_rating": "A",
            "prior_rating": "A",
            "spread_change_bps": 5.0,
            "spread_bps": 100.0,
            "spread_2s10s": 50.0,
            "prior_2s10s": 45.0,
            "current_regime": "NORMAL",
            "prior_regime": "NORMAL",
        }
        alerts = evaluate_fi_alerts(data)
        assert alerts == []

    def test_custom_config(self):
        data = {
            "spread_change_bps": 15.0,
            "spread_bps": 350.0,
        }
        config = {"spread_threshold": 10.0, "distress_threshold": 300.0}
        alerts = evaluate_fi_alerts(data, fi_config=config)
        alert_types = {a["alert_type"] for a in alerts}
        assert "SPREAD_WIDENING" in alert_types
        assert "DISTRESS_THRESHOLD" in alert_types


# ── check_score_change ────────────────────────────────────────────────────


class TestCheckScoreChange:
    def test_significant_change(self):
        result = check_score_change(8.0, 4.0, "PIOTROSKI", 3.0)
        assert result is not None
        assert "increased" in result["detail"]

    def test_no_change(self):
        assert check_score_change(5.0, 4.5, "PIOTROSKI", 3.0) is None

    def test_decrease(self):
        result = check_score_change(2.0, 7.0, "PIOTROSKI", 3.0)
        assert result is not None
        assert "decreased" in result["detail"]


# ── evaluate_quality_alerts ───────────────────────────────────────────────


class TestEvaluateQualityAlerts:
    def test_piotroski_change(self):
        current = {"piotroski": 8.0, "altman_z": 3.5, "beneish_m": -2.5}
        prior = {"piotroski": 4.0, "altman_z": 3.5, "beneish_m": -2.5}
        alerts = evaluate_quality_alerts(current, prior)
        types = {a["alert_type"] for a in alerts}
        assert "PIOTROSKI_CHANGE" in types

    def test_altman_zone_change(self):
        current = {"piotroski": 5.0, "altman_z": 1.5, "beneish_m": -2.5}
        prior = {"piotroski": 5.0, "altman_z": 2.5, "beneish_m": -2.5}
        alerts = evaluate_quality_alerts(current, prior)
        types = {a["alert_type"] for a in alerts}
        assert "ALTMAN_ZONE_CHANGE" in types

    def test_beneish_flag(self):
        current = {"piotroski": 5.0, "altman_z": 3.0, "beneish_m": -1.5}
        prior = {"piotroski": 5.0, "altman_z": 3.0, "beneish_m": -2.5}
        alerts = evaluate_quality_alerts(current, prior)
        types = {a["alert_type"] for a in alerts}
        assert "BENEISH_FLAG" in types

    def test_governance_decline(self):
        current = {"governance_score": 55.0}
        prior = {"governance_score": 80.0}
        alerts = evaluate_quality_alerts(current, prior)
        types = {a["alert_type"] for a in alerts}
        assert "GOVERNANCE_DETERIORATION" in types

    def test_no_quality_alerts(self):
        current = {"piotroski": 6.0, "altman_z": 3.5, "beneish_m": -3.0, "governance_score": 75.0}
        prior = {"piotroski": 5.0, "altman_z": 3.2, "beneish_m": -3.5, "governance_score": 78.0}
        alerts = evaluate_quality_alerts(current, prior)
        assert alerts == []

    def test_altman_distress_severity(self):
        current = {"altman_z": 1.5}
        prior = {"altman_z": 2.5}
        alerts = evaluate_quality_alerts(current, prior)
        distress_alert = next((a for a in alerts if a["alert_type"] == "ALTMAN_ZONE_CHANGE"), None)
        assert distress_alert is not None
        assert distress_alert["severity"] == "CRITICAL"


# ── evaluate_flow_alerts ──────────────────────────────────────────────────


class TestEvaluateFlowAlerts:
    def test_whale_move(self):
        data = {
            "whale_moves": [{"institution": "BigFund", "size_mm": 200.0, "direction": "bought"}],
        }
        alerts = evaluate_flow_alerts(data)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "WHALE_MOVE"

    def test_small_whale_ignored(self):
        data = {
            "whale_moves": [{"institution": "SmallFund", "size_mm": 50.0, "direction": "bought"}],
        }
        alerts = evaluate_flow_alerts(data)
        assert alerts == []

    def test_activist_13d(self):
        data = {
            "activist_filings": [{"activist": "Icahn", "stake_pct": 8.5}],
        }
        alerts = evaluate_flow_alerts(data)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "ACTIVIST_13D"
        assert alerts[0]["severity"] == "CRITICAL"

    def test_cluster_buy(self):
        data = {"cluster_buys": 5}
        alerts = evaluate_flow_alerts(data)
        types = {a["alert_type"] for a in alerts}
        assert "CLUSTER_BUY" in types

    def test_cluster_sell(self):
        data = {"cluster_sells": 4}
        alerts = evaluate_flow_alerts(data)
        types = {a["alert_type"] for a in alerts}
        assert "CLUSTER_SELL" in types

    def test_short_spike(self):
        data = {"short_interest_change_pct": 30.0}
        alerts = evaluate_flow_alerts(data)
        types = {a["alert_type"] for a in alerts}
        assert "SHORT_SPIKE" in types

    def test_insider_cluster_buy(self):
        data = {
            "insider_transactions": [
                {"direction": "BUY", "amount": 50000},
                {"direction": "BUY", "amount": 75000},
                {"direction": "BUY", "amount": 100000},
            ],
        }
        alerts = evaluate_flow_alerts(data)
        types = {a["alert_type"] for a in alerts}
        assert "INSIDER_CLUSTER" in types

    def test_no_flow_alerts(self):
        data = {
            "whale_moves": [],
            "activist_filings": [],
            "cluster_buys": 1,
            "cluster_sells": 0,
            "short_interest_change_pct": 5.0,
            "insider_transactions": [],
        }
        alerts = evaluate_flow_alerts(data)
        assert alerts == []


# ── prioritize_alerts ─────────────────────────────────────────────────────


class TestPrioritizeAlerts:
    def test_sort_order(self):
        alerts = [
            {"alert_type": "A", "severity": "LOW", "detail": "low"},
            {"alert_type": "B", "severity": "CRITICAL", "detail": "crit"},
            {"alert_type": "C", "severity": "MEDIUM", "detail": "med"},
            {"alert_type": "D", "severity": "HIGH", "detail": "high"},
        ]
        sorted_alerts = prioritize_alerts(alerts)
        assert sorted_alerts[0]["severity"] == "CRITICAL"
        assert sorted_alerts[1]["severity"] == "HIGH"
        assert sorted_alerts[2]["severity"] == "MEDIUM"
        assert sorted_alerts[3]["severity"] == "LOW"

    def test_empty_list(self):
        assert prioritize_alerts([]) == []

    def test_single_alert(self):
        alerts = [{"alert_type": "X", "severity": "HIGH", "detail": "test"}]
        assert len(prioritize_alerts(alerts)) == 1

    def test_same_severity(self):
        alerts = [
            {"alert_type": "A", "severity": "HIGH", "detail": "first"},
            {"alert_type": "B", "severity": "HIGH", "detail": "second"},
        ]
        result = prioritize_alerts(alerts)
        assert len(result) == 2
        assert all(a["severity"] == "HIGH" for a in result)
