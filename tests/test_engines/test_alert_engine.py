"""Tests for Pillar 3 Phase 1 — Part 8: Alert Engine."""

import pytest

from src.engines.alert_engine import (
    ALL_ALERT_TYPES,
    FILING_ALERT_TYPES,
    PRIORITY_ORDER,
    AlertResult,
    evaluate_filing_alerts,
    evaluate_governance_alerts,
    evaluate_insider_alerts,
    evaluate_price_alerts,
    format_alert_title,
    prioritize_alerts,
)


# ── Test Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def universe_rule():
    """Rule matching all entities for any filing alert."""
    return {
        "alert_type": "*",
        "entity_scope": {"type": "UNIVERSE"},
        "priority_threshold": "LOW",
        "is_active": True,
    }


@pytest.fixture
def watchlist_rule():
    """Rule matching only watchlist entities."""
    return {
        "alert_type": "FILING_8K",
        "entity_scope": {"type": "WATCHLIST", "entity_ids": ["ent-001", "ent-002"]},
        "priority_threshold": "LOW",
        "is_active": True,
    }


# ── Filing Alert Tests ────────────────────────────────────────────────────


class TestEvaluateFilingAlerts:

    def test_matching_event_triggers_alert(self, universe_rule):
        events = [{
            "alert_type": "RESTATEMENT",
            "entity_id": "ent-001",
            "entity_name": "ACME Corp",
            "priority": "CRITICAL",
            "detail": {},
        }]
        alerts = evaluate_filing_alerts(events, [universe_rule])
        assert len(alerts) == 1
        assert alerts[0].alert_type == "RESTATEMENT"
        assert alerts[0].priority == "CRITICAL"

    def test_inactive_rule_skipped(self):
        rule = {"alert_type": "*", "entity_scope": {"type": "UNIVERSE"}, "is_active": False}
        events = [{"alert_type": "FILING_8K", "entity_id": "ent-001", "priority": "HIGH"}]
        alerts = evaluate_filing_alerts(events, [rule])
        assert len(alerts) == 0

    def test_watchlist_scope_filters(self, watchlist_rule):
        events = [
            {"alert_type": "FILING_8K", "entity_id": "ent-001", "priority": "HIGH", "entity_name": "In Watchlist"},
            {"alert_type": "FILING_8K", "entity_id": "ent-999", "priority": "HIGH", "entity_name": "Not In Watchlist"},
        ]
        alerts = evaluate_filing_alerts(events, [watchlist_rule])
        assert len(alerts) == 1
        assert alerts[0].entity_id == "ent-001"

    def test_priority_threshold_filters(self):
        rule = {
            "alert_type": "*",
            "entity_scope": {"type": "UNIVERSE"},
            "priority_threshold": "HIGH",
            "is_active": True,
        }
        events = [
            {"alert_type": "FILING_8K", "entity_id": "ent-001", "priority": "HIGH"},
            {"alert_type": "FILING_ANNUAL", "entity_id": "ent-002", "priority": "MEDIUM"},
            {"alert_type": "RESTATEMENT", "entity_id": "ent-003", "priority": "CRITICAL"},
        ]
        alerts = evaluate_filing_alerts(events, [rule])
        # Only HIGH and CRITICAL should pass
        assert len(alerts) == 2
        types = {a.alert_type for a in alerts}
        assert "FILING_8K" in types
        assert "RESTATEMENT" in types

    def test_type_mismatch_no_alert(self):
        rule = {
            "alert_type": "RESTATEMENT",
            "entity_scope": {"type": "UNIVERSE"},
            "priority_threshold": "LOW",
            "is_active": True,
        }
        events = [{"alert_type": "FILING_8K", "entity_id": "ent-001", "priority": "HIGH"}]
        alerts = evaluate_filing_alerts(events, [rule])
        assert len(alerts) == 0

    def test_empty_events(self, universe_rule):
        alerts = evaluate_filing_alerts([], [universe_rule])
        assert len(alerts) == 0

    def test_empty_rules(self):
        events = [{"alert_type": "FILING_8K", "entity_id": "ent-001", "priority": "HIGH"}]
        alerts = evaluate_filing_alerts(events, [])
        assert len(alerts) == 0


# ── Price Alert Tests ─────────────────────────────────────────────────────


class TestEvaluatePriceAlerts:

    def test_threshold_gt_triggered(self):
        rules = [{
            "alert_type": "PRICE_THRESHOLD",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "conditions": {"operator": "GT", "value": 100},
            "is_active": True,
        }]
        prices = {"ent-001": 105.50}
        alerts = evaluate_price_alerts(prices, rules)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "PRICE_THRESHOLD"

    def test_threshold_lt_triggered(self):
        rules = [{
            "alert_type": "PRICE_THRESHOLD",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "conditions": {"operator": "LT", "value": 50},
            "is_active": True,
        }]
        prices = {"ent-001": 45.00}
        alerts = evaluate_price_alerts(prices, rules)
        assert len(alerts) == 1

    def test_threshold_not_triggered(self):
        rules = [{
            "alert_type": "PRICE_THRESHOLD",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "conditions": {"operator": "GT", "value": 200},
            "is_active": True,
        }]
        prices = {"ent-001": 150.00}
        alerts = evaluate_price_alerts(prices, rules)
        assert len(alerts) == 0

    def test_52w_high(self):
        rules = [{
            "alert_type": "PRICE_52W_HIGH",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "is_active": True,
        }]
        prices = {"ent-001": 155.00}
        highs = {"ent-001": 150.00}
        alerts = evaluate_price_alerts(prices, rules, historical_highs=highs)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "PRICE_52W_HIGH"

    def test_52w_low(self):
        rules = [{
            "alert_type": "PRICE_52W_LOW",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "is_active": True,
        }]
        prices = {"ent-001": 80.00}
        lows = {"ent-001": 85.00}
        alerts = evaluate_price_alerts(prices, rules, historical_lows=lows)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "PRICE_52W_LOW"

    def test_52w_high_not_triggered(self):
        rules = [{
            "alert_type": "PRICE_52W_HIGH",
            "entity_scope": {"entity_ids": ["ent-001"]},
            "is_active": True,
        }]
        prices = {"ent-001": 140.00}
        highs = {"ent-001": 150.00}
        alerts = evaluate_price_alerts(prices, rules, historical_highs=highs)
        assert len(alerts) == 0


# ── Insider Alert Tests ───────────────────────────────────────────────────


class TestEvaluateInsiderAlerts:

    def test_cluster_buy_alert(self):
        signals = [{
            "entity_id": "ent-001",
            "entity_name": "ACME Corp",
            "signal_type": "CLUSTER_BUY",
            "signal_strength": 80,
            "detail": {"insider_count": 4},
        }]
        rules = [{"alert_type": "*", "entity_scope": {"type": "UNIVERSE"}, "is_active": True}]
        alerts = evaluate_insider_alerts(signals, rules)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "INSIDER_CLUSTER_BUY"

    def test_ceo_purchase_alert(self):
        signals = [{
            "entity_id": "ent-001",
            "entity_name": "ACME Corp",
            "signal_type": "CEO_PURCHASE",
            "detail": {"shares": 50000},
        }]
        rules = [{"alert_type": "INSIDER_CEO_PURCHASE", "entity_scope": {"type": "UNIVERSE"}, "is_active": True}]
        alerts = evaluate_insider_alerts(signals, rules)
        assert len(alerts) == 1

    def test_unusual_sale_no_alert(self):
        signals = [{"entity_id": "ent-001", "signal_type": "UNUSUAL_SALE"}]
        rules = [{"alert_type": "*", "entity_scope": {"type": "UNIVERSE"}, "is_active": True}]
        alerts = evaluate_insider_alerts(signals, rules)
        assert len(alerts) == 0  # UNUSUAL_SALE not mapped to an alert type


# ── Governance Alert Tests ────────────────────────────────────────────────


class TestEvaluateGovernanceAlerts:

    def test_red_flag_alert(self):
        assessments = [{
            "entity_id": "ent-001",
            "entity_name": "ACME Corp",
            "governance_score": 55,
            "classification": "CONCERNS",
            "red_flags": [
                {"flag": "dual_class", "severity": "HIGH"},
                {"flag": "ceo_is_chair", "severity": "MEDIUM"},
            ],
        }]
        rules = [{"alert_type": "GOVERNANCE_RED_FLAG", "entity_scope": {"type": "UNIVERSE"}, "is_active": True}]
        alerts = evaluate_governance_alerts(assessments, rules)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "GOVERNANCE_RED_FLAG"
        assert "dual_class" in alerts[0].title

    def test_no_red_flags_no_alert(self):
        assessments = [{
            "entity_id": "ent-001",
            "governance_score": 95,
            "classification": "STRONG",
            "red_flags": [],
        }]
        rules = [{"alert_type": "GOVERNANCE_RED_FLAG", "entity_scope": {"type": "UNIVERSE"}, "is_active": True}]
        alerts = evaluate_governance_alerts(assessments, rules)
        assert len(alerts) == 0


# ── Alert Prioritization Tests ────────────────────────────────────────────


class TestPrioritizeAlerts:

    def test_sort_by_priority(self):
        alerts = [
            AlertResult(alert_type="LOW_ALERT", priority="LOW", entity_id="e1"),
            AlertResult(alert_type="CRITICAL_ALERT", priority="CRITICAL", entity_id="e2"),
            AlertResult(alert_type="HIGH_ALERT", priority="HIGH", entity_id="e3"),
        ]
        result = prioritize_alerts(alerts)
        assert result[0].priority == "CRITICAL"
        assert result[1].priority == "HIGH"
        assert result[2].priority == "LOW"

    def test_dedup_same_type_entity(self):
        alerts = [
            AlertResult(alert_type="FILING_8K", priority="HIGH", entity_id="e1"),
            AlertResult(alert_type="FILING_8K", priority="HIGH", entity_id="e1"),
        ]
        result = prioritize_alerts(alerts)
        assert len(result) == 1

    def test_different_types_not_deduped(self):
        alerts = [
            AlertResult(alert_type="FILING_8K", priority="HIGH", entity_id="e1"),
            AlertResult(alert_type="RESTATEMENT", priority="CRITICAL", entity_id="e1"),
        ]
        result = prioritize_alerts(alerts)
        assert len(result) == 2

    def test_rate_limit_per_entity(self):
        alerts = [
            AlertResult(alert_type=f"TYPE_{i}", priority="HIGH", entity_id="e1")
            for i in range(20)
        ]
        result = prioritize_alerts(alerts, max_per_entity=5)
        assert len(result) == 5

    def test_empty_alerts(self):
        assert prioritize_alerts([]) == []


# ── Alert Title Formatting Tests ──────────────────────────────────────────


class TestFormatAlertTitle:

    def test_restatement_title(self):
        title = format_alert_title("RESTATEMENT", "ACME Corp", {})
        assert "CRITICAL" in title
        assert "ACME Corp" in title
        assert "non-reliance" in title

    def test_management_change_with_person(self):
        detail = {"key_people": [{"name": "John Smith", "role": "CEO", "action": "resigned"}]}
        title = format_alert_title("MANAGEMENT_CHANGE", "ACME Corp", detail)
        assert "John Smith" in title

    def test_management_change_no_person(self):
        title = format_alert_title("MANAGEMENT_CHANGE", "ACME Corp", {})
        assert "ACME Corp" in title

    def test_cluster_buy_title(self):
        detail = {"insider_count": 5}
        title = format_alert_title("INSIDER_CLUSTER_BUY", "ACME Corp", detail)
        assert "5" in title
        assert "insiders" in title

    def test_52w_high_title(self):
        detail = {"price": 155.30}
        title = format_alert_title("PRICE_52W_HIGH", "ACME Corp", detail)
        assert "52-week high" in title
        assert "$155.30" in title

    def test_unknown_type_fallback(self):
        title = format_alert_title("UNKNOWN_TYPE", "ACME Corp", {})
        assert "ACME Corp" in title


# ── Constants Tests ───────────────────────────────────────────────────────


class TestConstants:

    def test_all_filing_alert_types_defined(self):
        expected = [
            "FILING_8K", "FILING_ANNUAL", "RISK_FACTOR_CHANGE",
            "AUDITOR_CHANGE", "RESTATEMENT", "MANAGEMENT_CHANGE",
            "INSIDER_CLUSTER_BUY", "INSIDER_CEO_PURCHASE", "GOVERNANCE_RED_FLAG",
        ]
        for t in expected:
            assert t in FILING_ALERT_TYPES

    def test_all_alert_types_have_priority(self):
        for alert_type, config in ALL_ALERT_TYPES.items():
            assert "priority" in config
            assert config["priority"] in PRIORITY_ORDER

    def test_priority_ordering(self):
        assert PRIORITY_ORDER["CRITICAL"] > PRIORITY_ORDER["HIGH"]
        assert PRIORITY_ORDER["HIGH"] > PRIORITY_ORDER["MEDIUM"]
        assert PRIORITY_ORDER["MEDIUM"] > PRIORITY_ORDER["LOW"]
