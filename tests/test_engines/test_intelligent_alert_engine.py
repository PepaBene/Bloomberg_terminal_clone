"""Tests for Pillar 3 Phase 4C — Engine 3: Intelligent Alert Engine."""

import pytest
from datetime import datetime, timezone, timedelta

from src.engines.intelligent_alert_engine import (
    ALERT_CATEGORIES,
    DEDUP_WINDOW_HOURS,
    MAX_ALERTS_PER_ENTITY,
    PRIORITY_SCORES,
    apply_fatigue_reduction,
    classify_alert_category,
    compute_alert_priority,
    consolidate_alerts,
    deduplicate_alerts,
    filter_low_signal,
    generate_alert_synthesis_template,
    process_alert_batch,
    recommend_action,
    route_alert,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _now():
    return datetime.now(timezone.utc)


def _make_alert(
    entity_id: str = "e1",
    alert_type: str = "earnings_miss",
    headline: str = "Company missed earnings",
    timestamp: datetime | None = None,
    priority: int | None = None,
    alert_id: str | None = None,
    magnitude: float | None = None,
) -> dict:
    return {
        "entity_id": entity_id,
        "alert_type": alert_type,
        "headline": headline,
        "timestamp": (timestamp or _now()).isoformat(),
        "priority": priority or PRIORITY_SCORES.get(alert_type, 25),
        "alert_id": alert_id or f"a-{entity_id}-{alert_type}",
        "magnitude": magnitude,
    }


# ── Constants Tests ──────────────────────────────────────────────────────


class TestConstants:
    def test_dedup_window(self):
        assert DEDUP_WINDOW_HOURS == 2

    def test_max_alerts_per_entity(self):
        assert MAX_ALERTS_PER_ENTITY == 5

    def test_priority_scores_non_empty(self):
        assert len(PRIORITY_SCORES) > 0

    def test_all_priorities_in_range(self):
        for alert_type, score in PRIORITY_SCORES.items():
            assert 0 <= score <= 100, f"{alert_type} priority {score} out of range"

    def test_earnings_miss_high_priority(self):
        assert PRIORITY_SCORES["earnings_miss"] >= 90

    def test_alert_categories_match_priority_keys(self):
        for key in PRIORITY_SCORES:
            assert key in ALERT_CATEGORIES


# ── classify_alert_category Tests ────────────────────────────────────────


class TestClassifyAlertCategory:
    def test_earnings_miss_category(self):
        assert classify_alert_category("earnings_miss") == "EARNINGS"

    def test_rating_downgrade_category(self):
        assert classify_alert_category("rating_downgrade") == "RATING"

    def test_ceo_departure_category(self):
        assert classify_alert_category("ceo_departure") == "MANAGEMENT"

    def test_sec_investigation_category(self):
        assert classify_alert_category("sec_investigation") == "REGULATORY"

    def test_unknown_type_returns_other(self):
        assert classify_alert_category("totally_unknown") == "OTHER"

    def test_insider_selling_category(self):
        assert classify_alert_category("insider_selling") == "INSIDER"


# ── compute_alert_priority Tests ─────────────────────────────────────────


class TestComputeAlertPriority:
    def test_base_priority(self):
        priority = compute_alert_priority("earnings_miss")
        assert priority == PRIORITY_SCORES["earnings_miss"] + 5  # +5 for market hours

    def test_portfolio_boost(self):
        base = compute_alert_priority("news_negative", entity_in_portfolio=False)
        boosted = compute_alert_priority("news_negative", entity_in_portfolio=True)
        assert boosted > base

    def test_magnitude_boost_large(self):
        base = compute_alert_priority("price_move", magnitude=None)
        large = compute_alert_priority("price_move", magnitude=25.0)
        assert large > base

    def test_magnitude_boost_moderate(self):
        base = compute_alert_priority("price_move", magnitude=None)
        moderate = compute_alert_priority("price_move", magnitude=12.0)
        assert moderate > base

    def test_market_hours_boost(self):
        mh = compute_alert_priority("filing_8k", market_hours=True)
        ah = compute_alert_priority("filing_8k", market_hours=False)
        assert mh > ah

    def test_capped_at_100(self):
        priority = compute_alert_priority(
            "earnings_miss", magnitude=50.0,
            entity_in_portfolio=True, market_hours=True,
        )
        assert priority <= 100

    def test_floored_at_0(self):
        priority = compute_alert_priority("unknown_type")
        assert priority >= 0

    def test_unknown_type_gets_default(self):
        priority = compute_alert_priority("unknown_type", market_hours=False)
        assert priority == 25


# ── deduplicate_alerts Tests ─────────────────────────────────────────────


class TestDeduplicateAlerts:
    def test_no_duplicates_passed_through(self):
        alerts = [
            _make_alert("e1", "earnings_miss"),
            _make_alert("e2", "rating_downgrade"),
        ]
        result = deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_duplicate_within_window_removed(self):
        t1 = _now()
        t2 = t1 + timedelta(hours=1)
        alerts = [
            _make_alert("e1", "earnings_miss", timestamp=t1),
            _make_alert("e1", "earnings_miss", timestamp=t2),
        ]
        result = deduplicate_alerts(alerts)
        assert len(result) == 1

    def test_duplicate_outside_window_kept(self):
        t1 = _now()
        t2 = t1 + timedelta(hours=3)
        alerts = [
            _make_alert("e1", "earnings_miss", timestamp=t1),
            _make_alert("e1", "earnings_miss", timestamp=t2),
        ]
        result = deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_different_types_not_deduped(self):
        t = _now()
        alerts = [
            _make_alert("e1", "earnings_miss", timestamp=t),
            _make_alert("e1", "guidance_cut", timestamp=t),
        ]
        result = deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_different_entities_not_deduped(self):
        t = _now()
        alerts = [
            _make_alert("e1", "earnings_miss", timestamp=t),
            _make_alert("e2", "earnings_miss", timestamp=t),
        ]
        result = deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_empty_input(self):
        assert deduplicate_alerts([]) == []


# ── consolidate_alerts Tests ─────────────────────────────────────────────


class TestConsolidateAlerts:
    def test_single_entity_consolidation(self):
        alerts = [
            _make_alert("e1", "earnings_miss", priority=95, headline="Missed EPS"),
            _make_alert("e1", "guidance_cut", priority=90, headline="Cut guidance"),
        ]
        result = consolidate_alerts(alerts)
        assert len(result) == 1
        assert result[0]["primary_headline"] == "Missed EPS"
        assert len(result[0]["secondary_alerts"]) == 1

    def test_multiple_entities(self):
        alerts = [
            _make_alert("e1", "earnings_miss", priority=95),
            _make_alert("e2", "ceo_departure", priority=85),
        ]
        result = consolidate_alerts(alerts)
        assert len(result) == 2

    def test_sorted_by_priority_descending(self):
        alerts = [
            _make_alert("e1", "price_move", priority=30),
            _make_alert("e2", "earnings_miss", priority=95),
        ]
        result = consolidate_alerts(alerts)
        priorities = [r["alert_priority"] for r in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_categories_collected(self):
        alerts = [
            _make_alert("e1", "earnings_miss", priority=95),
            _make_alert("e1", "insider_selling", priority=70),
        ]
        result = consolidate_alerts(alerts)
        categories = result[0]["alert_categories"]
        assert "EARNINGS" in categories
        assert "INSIDER" in categories

    def test_empty_input(self):
        assert consolidate_alerts([]) == []

    def test_max_secondary_alerts(self):
        alerts = [
            _make_alert("e1", f"type_{i}", priority=90 - i, headline=f"Alert {i}")
            for i in range(8)
        ]
        result = consolidate_alerts(alerts)
        # Secondary should be capped at MAX_ALERTS_PER_ENTITY - 1
        assert len(result[0]["secondary_alerts"]) <= MAX_ALERTS_PER_ENTITY - 1


# ── filter_low_signal Tests ──────────────────────────────────────────────


class TestFilterLowSignal:
    def test_removes_below_threshold(self):
        alerts = [
            {"priority": 80},
            {"priority": 20},
            {"priority": 50},
        ]
        result = filter_low_signal(alerts, min_priority=30)
        assert len(result) == 2

    def test_keeps_at_threshold(self):
        alerts = [{"priority": 30}]
        result = filter_low_signal(alerts, min_priority=30)
        assert len(result) == 1

    def test_uses_alert_priority_key(self):
        alerts = [{"alert_priority": 60}]
        result = filter_low_signal(alerts, min_priority=50)
        assert len(result) == 1

    def test_empty_input(self):
        assert filter_low_signal([], min_priority=30) == []


# ── apply_fatigue_reduction Tests ────────────────────────────────────────


class TestApplyFatigueReduction:
    def test_limits_per_entity(self):
        alerts = [
            {"entity_id": "e1", "alert_priority": 90 - i}
            for i in range(10)
        ]
        result = apply_fatigue_reduction(alerts, max_per_entity=3, max_total=50)
        assert len(result) == 3

    def test_limits_total(self):
        alerts = [
            {"entity_id": f"e{i}", "alert_priority": 50}
            for i in range(30)
        ]
        result = apply_fatigue_reduction(alerts, max_per_entity=10, max_total=15)
        assert len(result) == 15

    def test_empty_input(self):
        assert apply_fatigue_reduction([]) == []


# ── generate_alert_synthesis_template Tests ──────────────────────────────


class TestGenerateAlertSynthesis:
    def test_includes_headline(self):
        consolidated = {
            "primary_headline": "Company X missed EPS",
            "primary_type": "earnings_miss",
            "alert_priority": 95,
            "secondary_alerts": [],
            "alert_categories": ["EARNINGS"],
        }
        synthesis = generate_alert_synthesis_template(consolidated)
        assert "Company X missed EPS" in synthesis

    def test_includes_secondary(self):
        consolidated = {
            "primary_headline": "Main Alert",
            "primary_type": "earnings_miss",
            "alert_priority": 95,
            "secondary_alerts": [
                {"headline": "Sub Alert 1", "alert_type": "guidance_cut", "priority": 90},
            ],
            "alert_categories": ["EARNINGS"],
        }
        synthesis = generate_alert_synthesis_template(consolidated)
        assert "Related alerts" in synthesis

    def test_includes_categories(self):
        consolidated = {
            "primary_headline": "Test",
            "primary_type": "earnings_miss",
            "alert_priority": 95,
            "secondary_alerts": [],
            "alert_categories": ["EARNINGS", "RATING"],
        }
        synthesis = generate_alert_synthesis_template(consolidated)
        assert "Categories" in synthesis


# ── recommend_action Tests ───────────────────────────────────────────────


class TestRecommendAction:
    def test_high_priority_review_immediately(self):
        assert recommend_action(90) == "REVIEW_IMMEDIATELY"

    def test_medium_priority_review_today(self):
        assert recommend_action(70) == "REVIEW_TODAY"

    def test_low_priority_monitor(self):
        assert recommend_action(45) == "MONITOR"

    def test_very_low_informational(self):
        assert recommend_action(10) == "INFORMATIONAL"

    def test_boundary_85(self):
        assert recommend_action(85) == "REVIEW_IMMEDIATELY"

    def test_boundary_65(self):
        assert recommend_action(65) == "REVIEW_TODAY"


# ── route_alert Tests ────────────────────────────────────────────────────


class TestRouteAlert:
    def test_high_priority_to_pm(self):
        result = route_alert({"priority": 90, "alert_type": "earnings_miss"})
        assert result["destination"] == "portfolio_manager"
        assert result["escalate"] is True

    def test_medium_priority_to_analyst(self):
        result = route_alert({"priority": 70, "alert_type": "analyst_downgrade"})
        assert result["destination"] == "research_analyst"
        assert result["channel"] == "push"

    def test_low_priority_to_email(self):
        result = route_alert({"priority": 45, "alert_type": "filing_10k"})
        assert result["destination"] == "research_analyst"
        assert result["channel"] == "email"

    def test_very_low_to_digest(self):
        result = route_alert({"priority": 20, "alert_type": "volume_spike"})
        assert result["destination"] == "digest"

    def test_custom_routing_rules(self):
        rules = {
            "earnings_miss": {"destination": "trading_desk", "channel": "sms"},
        }
        result = route_alert({"priority": 95, "alert_type": "earnings_miss"}, routing_rules=rules)
        assert result["destination"] == "trading_desk"
        assert result["channel"] == "sms"

    def test_custom_rules_fallback(self):
        rules = {"earnings_miss": {"destination": "trading_desk", "channel": "sms"}}
        result = route_alert({"priority": 70, "alert_type": "filing_8k"}, routing_rules=rules)
        assert result["destination"] == "research_analyst"


# ── process_alert_batch Tests ────────────────────────────────────────────


class TestProcessAlertBatch:
    def test_end_to_end_pipeline(self):
        raw = [
            _make_alert("e1", "earnings_miss", headline="E1 missed EPS"),
            _make_alert("e1", "guidance_cut", headline="E1 cut guidance"),
            _make_alert("e2", "ceo_departure", headline="E2 CEO left"),
        ]
        result = process_alert_batch(raw)
        assert len(result) >= 1
        for alert in result:
            assert "recommended_action" in alert
            assert "routing" in alert
            assert "ai_synthesis" in alert

    def test_portfolio_entities_boosted(self):
        raw = [
            _make_alert("e1", "news_negative", headline="Bad news for E1"),
            _make_alert("e2", "news_negative", headline="Bad news for E2"),
        ]
        result = process_alert_batch(raw, portfolio_entity_ids={"e1"})
        # E1 should have higher priority due to portfolio boost
        e1_alert = next((a for a in result if a.get("entity_id") == "e1"), None)
        e2_alert = next((a for a in result if a.get("entity_id") == "e2"), None)
        if e1_alert and e2_alert:
            assert e1_alert["alert_priority"] >= e2_alert["alert_priority"]

    def test_low_signal_filtered(self):
        raw = [
            _make_alert("e1", "volume_spike", headline="Volume spike"),
        ]
        result = process_alert_batch(raw, min_priority=50)
        # volume_spike has base priority 35 + 5 market hours = 40, below 50
        assert len(result) == 0

    def test_empty_batch(self):
        result = process_alert_batch([])
        assert result == []

    def test_max_total_respected(self):
        raw = [
            _make_alert(f"e{i}", "earnings_miss", headline=f"Alert {i}")
            for i in range(30)
        ]
        result = process_alert_batch(raw, max_total=5)
        assert len(result) <= 5
