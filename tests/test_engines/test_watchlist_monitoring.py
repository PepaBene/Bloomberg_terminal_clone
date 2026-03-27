"""Tests for Pillar 4 Phase 1 — Watchlist Monitoring Engine."""

from datetime import datetime, timedelta

import pytest

from src.engines.watchlist_monitoring import (
    ALERT_TYPES,
    SCORE_CHANGE_THRESHOLDS,
    PriceAlert,
    ScoreChangeAlert,
    ValuationAlert,
    WatchlistAlert,
    WatchlistMonitorResult,
    check_earnings_calendar,
    check_filing_alert,
    check_institutional_flow,
    check_news_alert,
    check_price_alert,
    check_score_change,
    check_valuation_alert,
    evaluate_watchlist_alerts,
    filter_by_user_preferences,
    format_alert_digest,
)


# ── TestPriceAlert ────────────────────────────────────────────────────────


class TestPriceAlert:
    def test_above_threshold(self):
        """Price above threshold with ABOVE direction triggers."""
        result = check_price_alert(155.0, [{"threshold": 150.0, "direction": "ABOVE"}])
        assert len(result) == 1
        assert result[0].direction == "ABOVE"
        assert result[0].current_price == 155.0
        assert result[0].threshold_price == 150.0
        assert result[0].pct_from_threshold > 0

    def test_below_threshold(self):
        """Price below threshold with BELOW direction triggers."""
        result = check_price_alert(95.0, [{"threshold": 100.0, "direction": "BELOW"}])
        assert len(result) == 1
        assert result[0].direction == "BELOW"
        assert result[0].current_price == 95.0
        assert result[0].threshold_price == 100.0

    def test_no_trigger(self):
        """Price above threshold with BELOW direction does NOT trigger."""
        result = check_price_alert(155.0, [{"threshold": 150.0, "direction": "BELOW"}])
        assert len(result) == 0

    def test_multiple_rules(self):
        """Multiple rules — some trigger, some don't."""
        rules = [
            {"threshold": 100.0, "direction": "ABOVE"},   # triggers (120 > 100)
            {"threshold": 150.0, "direction": "ABOVE"},    # no trigger (120 < 150)
            {"threshold": 130.0, "direction": "BELOW"},    # triggers (120 <= 130)
        ]
        result = check_price_alert(120.0, rules)
        assert len(result) == 2
        directions = {r.direction for r in result}
        assert "ABOVE" in directions
        assert "BELOW" in directions


# ── TestValuationAlert ────────────────────────────────────────────────────


class TestValuationAlert:
    def test_below_entry_price(self):
        """Price at or below target entry triggers."""
        result = check_valuation_alert(95.0, 100.0, None, None)
        assert result is not None
        assert result.below_entry is True
        assert result.current_price == 95.0

    def test_below_target_pe(self):
        """Current P/E at or below target P/E triggers."""
        result = check_valuation_alert(150.0, None, 12.0, 15.0)
        assert result is not None
        assert result.current_pe == 12.0
        assert result.target_pe == 15.0

    def test_above_both_no_alert(self):
        """Price above target AND P/E above target — no alert."""
        result = check_valuation_alert(150.0, 100.0, 20.0, 15.0)
        assert result is None

    def test_partial_data(self):
        """Only price data, no P/E — triggers if below entry."""
        result = check_valuation_alert(90.0, 100.0, None, None)
        assert result is not None
        assert result.below_entry is True
        assert result.current_pe is None
        assert result.target_pe is None


# ── TestScoreChange ───────────────────────────────────────────────────────


class TestScoreChange:
    def test_piotroski_big_change(self):
        """Piotroski change of +4 triggers alert."""
        result = check_score_change(
            {"piotroski": 8, "altman": 3.0, "beneish": -2.5},
            {"piotroski": 4, "altman": 3.0, "beneish": -2.5},
        )
        pio = [a for a in result if a.score_name == "piotroski"]
        assert len(pio) == 1
        assert pio[0].change == 4.0
        assert pio[0].significance == "IMPROVED"

    def test_altman_zone_change(self):
        """Altman zone from SAFE (3.5) to GREY (2.5) triggers."""
        result = check_score_change(
            {"piotroski": 5, "altman": 2.5, "beneish": -2.5},
            {"piotroski": 5, "altman": 3.5, "beneish": -2.5},
        )
        alt = [a for a in result if a.score_name == "altman"]
        assert len(alt) == 1
        assert alt[0].significance == "DETERIORATED"

    def test_beneish_crossed(self):
        """Beneish crossed -1.78 threshold (below to above)."""
        result = check_score_change(
            {"piotroski": 5, "altman": 3.0, "beneish": -1.5},
            {"piotroski": 5, "altman": 3.0, "beneish": -2.5},
        )
        ben = [a for a in result if a.score_name == "beneish"]
        assert len(ben) == 1
        assert ben[0].significance == "DETERIORATED"

    def test_no_change(self):
        """No significant changes — no alerts."""
        result = check_score_change(
            {"piotroski": 5, "altman": 3.0, "beneish": -2.5},
            {"piotroski": 5, "altman": 3.0, "beneish": -2.5},
        )
        assert len(result) == 0


# ── TestFilingAlert ───────────────────────────────────────────────────────


class TestFilingAlert:
    def test_new_filings_after_last_check(self):
        """Two filings after last_checked are returned."""
        filings = [
            {"filing_type": "10-K", "filed_date": "2026-03-20", "title": "Annual", "url": "/10k"},
            {"filing_type": "8-K", "filed_date": "2026-03-22", "title": "Event", "url": "/8k"},
            {"filing_type": "10-Q", "filed_date": "2026-03-10", "title": "Old", "url": "/10q"},
        ]
        result = check_filing_alert(filings, "2026-03-15")
        assert len(result) == 2
        # 8-K should be first (priority filing type)
        assert result[0]["filing_type"] == "8-K"

    def test_none_new(self):
        """No filings after last_checked."""
        filings = [
            {"filing_type": "10-K", "filed_date": "2026-03-01", "title": "Old", "url": "/10k"},
        ]
        result = check_filing_alert(filings, "2026-03-15")
        assert len(result) == 0

    def test_8k_priority(self):
        """8-K filings appear before non-priority types."""
        filings = [
            {"filing_type": "10-Q", "filed_date": "2026-03-25", "title": "Quarterly", "url": "/10q"},
            {"filing_type": "8-K", "filed_date": "2026-03-20", "title": "Event", "url": "/8k"},
            {"filing_type": "SC 13D", "filed_date": "2026-03-21", "title": "Activist", "url": "/13d"},
        ]
        result = check_filing_alert(filings, "2026-03-15")
        assert len(result) == 3
        # Priority types first
        assert result[0]["filing_type"] in {"8-K", "SC 13D"}
        assert result[1]["filing_type"] in {"8-K", "SC 13D"}
        assert result[2]["filing_type"] == "10-Q"


# ── TestNewsAlert ─────────────────────────────────────────────────────────


class TestNewsAlert:
    def test_above_relevance(self):
        """Three articles above 0.5 relevance returned."""
        news = [
            {"title": "A", "source": "X", "relevance_score": 0.9, "sentiment": "positive"},
            {"title": "B", "source": "Y", "relevance_score": 0.7, "sentiment": "neutral"},
            {"title": "C", "source": "Z", "relevance_score": 0.6, "sentiment": "negative"},
            {"title": "D", "source": "W", "relevance_score": 0.3, "sentiment": "neutral"},
        ]
        result = check_news_alert(news, 0.5)
        assert len(result) == 3

    def test_none_above_threshold(self):
        """No articles above threshold."""
        news = [
            {"title": "A", "relevance_score": 0.2},
            {"title": "B", "relevance_score": 0.1},
        ]
        result = check_news_alert(news, 0.5)
        assert len(result) == 0

    def test_sorted_by_relevance(self):
        """Results sorted by relevance descending."""
        news = [
            {"title": "Low", "relevance_score": 0.6},
            {"title": "High", "relevance_score": 0.95},
            {"title": "Mid", "relevance_score": 0.8},
        ]
        result = check_news_alert(news, 0.5)
        assert len(result) == 3
        assert result[0]["title"] == "High"
        assert result[1]["title"] == "Mid"
        assert result[2]["title"] == "Low"


# ── TestInstitutionalFlow ─────────────────────────────────────────────────


class TestInstitutionalFlow:
    def test_whale_trade(self):
        """Whale trade $50M triggers alert."""
        flow = {
            "whale_trades": [{"institution": "BlackRock", "direction": "BUY", "value_mm": 50}],
            "activist_filings": [],
            "insider_transactions": [],
        }
        result = check_institutional_flow(flow)
        assert len(result) == 1
        assert result[0]["type"] == "WHALE_TRADE"
        assert result[0]["value_mm"] == 50

    def test_activist_13d(self):
        """Activist 13D filing triggers alert."""
        flow = {
            "whale_trades": [],
            "activist_filings": [{"activist": "Icahn", "stake_pct": 9.5}],
            "insider_transactions": [],
        }
        result = check_institutional_flow(flow)
        assert len(result) == 1
        assert result[0]["type"] == "ACTIVIST_13D"

    def test_no_significant_flow(self):
        """Small whale trade and no activists — no alerts."""
        flow = {
            "whale_trades": [{"institution": "Small Fund", "direction": "BUY", "value_mm": 5}],
            "activist_filings": [],
            "insider_transactions": [
                {"direction": "BUY"},
                {"direction": "SELL"},
            ],
        }
        result = check_institutional_flow(flow)
        assert len(result) == 0


# ── TestEarningsCalendar ──────────────────────────────────────────────────


class TestEarningsCalendar:
    def test_earnings_in_7_days(self):
        """Earnings 7 days out with 14-day window triggers."""
        future = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        entries = [{"ticker": "AAPL", "earnings_date": future, "is_confirmed": True}]
        result = check_earnings_calendar(entries, days_ahead=14)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["is_confirmed"] is True
        assert result[0]["days_until"] <= 7

    def test_earnings_beyond_window(self):
        """Earnings 30 days out with 14-day window — no alert."""
        future = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        entries = [{"ticker": "MSFT", "earnings_date": future, "is_confirmed": True}]
        result = check_earnings_calendar(entries, days_ahead=14)
        assert len(result) == 0

    def test_confirmed_vs_unconfirmed(self):
        """Both confirmed and unconfirmed earnings returned with flags."""
        d1 = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d")
        d2 = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d")
        entries = [
            {"ticker": "GOOG", "earnings_date": d1, "is_confirmed": True},
            {"ticker": "META", "earnings_date": d2, "is_confirmed": False},
        ]
        result = check_earnings_calendar(entries, days_ahead=14)
        assert len(result) == 2
        confirmed = [r for r in result if r["is_confirmed"]]
        unconfirmed = [r for r in result if not r["is_confirmed"]]
        assert len(confirmed) == 1
        assert len(unconfirmed) == 1


# ── TestEvaluateAll ───────────────────────────────────────────────────────


class TestEvaluateAll:
    def _make_entity(self) -> dict:
        """Full entity with multiple alert sources."""
        future_earnings = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        return {
            "entity_id": "ENT001",
            "ticker": "AAPL",
            "current_price": 145.0,
            "target_price": 150.0,
            "current_pe": 14.0,
            "target_pe": 15.0,
            "price_rules": [
                {"threshold": 150.0, "direction": "BELOW"},
            ],
            "scores": {"piotroski": 8, "altman": 2.0, "beneish": -1.5},
            "prior_scores": {"piotroski": 4, "altman": 3.5, "beneish": -2.5},
            "filings": [
                {"filing_type": "8-K", "filed_date": "2026-03-22", "title": "Event", "url": "/8k"},
            ],
            "last_checked": "2026-03-15",
            "news": [
                {"title": "Big news", "source": "Reuters", "relevance_score": 0.9, "sentiment": "positive"},
            ],
            "flows": {
                "whale_trades": [{"institution": "Vanguard", "direction": "BUY", "value_mm": 25}],
                "activist_filings": [],
                "insider_transactions": [],
            },
            "earnings": [
                {"ticker": "AAPL", "earnings_date": future_earnings, "is_confirmed": True},
            ],
        }

    def test_full_entity_multiple_alerts(self):
        """Full entity generates alerts from multiple sources."""
        result = evaluate_watchlist_alerts(self._make_entity())
        assert isinstance(result, WatchlistMonitorResult)
        assert result.entity_id == "ENT001"
        assert result.ticker == "AAPL"
        assert result.total_alerts > 0
        # Should have at least: price, valuation, score(s), filing, news, flow, earnings
        alert_types = {a.alert_type for a in result.alerts}
        assert "PRICE_THRESHOLD" in alert_types
        assert "SCORE_CHANGE" in alert_types
        assert result.high_priority > 0

    def test_clean_entity_no_alerts(self):
        """Entity with no trigger conditions produces zero alerts."""
        entity = {
            "entity_id": "ENT002",
            "ticker": "BORING",
            "current_price": 100.0,
            "price_rules": [],
            "scores": {},
            "prior_scores": {},
            "filings": [],
            "last_checked": "2026-03-25",
            "news": [],
            "flows": {},
            "earnings": [],
        }
        result = evaluate_watchlist_alerts(entity)
        assert result.total_alerts == 0
        assert result.high_priority == 0
        assert result.medium_priority == 0
        assert result.low_priority == 0

    def test_config_filtering(self):
        """Config mutes NEWS_ALERT and min_severity MEDIUM removes LOW."""
        entity = self._make_entity()
        config = {"muted_types": ["NEWS_ALERT"], "min_severity": "MEDIUM"}
        result = evaluate_watchlist_alerts(entity, alert_config=config)
        alert_types = {a.alert_type for a in result.alerts}
        assert "NEWS_ALERT" not in alert_types
        # LOW severity alerts should be filtered out
        assert result.low_priority == 0


# ── TestPreferences ───────────────────────────────────────────────────────


class TestPreferences:
    def _make_alerts(self) -> list[WatchlistAlert]:
        return [
            WatchlistAlert("PRICE_THRESHOLD", "E1", "AAPL", "HIGH", "Price", "msg", {}, ""),
            WatchlistAlert("NEWS_ALERT", "E1", "AAPL", "MEDIUM", "News", "msg", {}, ""),
            WatchlistAlert("INSTITUTIONAL_FLOW", "E1", "AAPL", "LOW", "Flow", "msg", {}, ""),
            WatchlistAlert("EARNINGS_CALENDAR", "E1", "AAPL", "LOW", "Earnings", "msg", {}, ""),
        ]

    def test_mute_news_alert(self):
        """Muting NEWS_ALERT removes only that type."""
        alerts = self._make_alerts()
        prefs = {"muted_types": ["NEWS_ALERT"]}
        result = filter_by_user_preferences(alerts, prefs)
        assert len(result) == 3
        types = {a.alert_type for a in result}
        assert "NEWS_ALERT" not in types

    def test_min_severity_medium(self):
        """min_severity MEDIUM filters out LOW alerts."""
        alerts = self._make_alerts()
        prefs = {"min_severity": "MEDIUM"}
        result = filter_by_user_preferences(alerts, prefs)
        assert len(result) == 2
        for a in result:
            assert a.severity in ("HIGH", "MEDIUM")


# ── TestDigest ────────────────────────────────────────────────────────────


class TestDigest:
    def test_mixed_alerts_formatted(self):
        """10 mixed alerts produce correct digest."""
        alerts = [
            WatchlistAlert("PRICE_THRESHOLD", "E1", "AAPL", "HIGH", "P1", "m", {}, ""),
            WatchlistAlert("PRICE_THRESHOLD", "E2", "MSFT", "HIGH", "P2", "m", {}, ""),
            WatchlistAlert("VALUATION_TARGET", "E1", "AAPL", "HIGH", "V1", "m", {}, ""),
            WatchlistAlert("SCORE_CHANGE", "E1", "AAPL", "MEDIUM", "S1", "m", {}, ""),
            WatchlistAlert("SCORE_CHANGE", "E2", "MSFT", "MEDIUM", "S2", "m", {}, ""),
            WatchlistAlert("FILING_EVENT", "E1", "AAPL", "MEDIUM", "F1", "m", {}, ""),
            WatchlistAlert("NEWS_ALERT", "E1", "AAPL", "MEDIUM", "N1", "m", {}, ""),
            WatchlistAlert("INSTITUTIONAL_FLOW", "E1", "AAPL", "LOW", "I1", "m", {}, ""),
            WatchlistAlert("EARNINGS_CALENDAR", "E1", "AAPL", "LOW", "EC1", "m", {}, ""),
            WatchlistAlert("EARNINGS_CALENDAR", "E2", "MSFT", "LOW", "EC2", "m", {}, ""),
        ]
        digest = format_alert_digest(alerts)

        assert digest["high_count"] == 3
        assert digest["medium_count"] == 4
        assert digest["low_count"] == 3

        assert digest["by_type"]["PRICE_THRESHOLD"] == 2
        assert digest["by_type"]["VALUATION_TARGET"] == 1
        assert digest["by_type"]["SCORE_CHANGE"] == 2
        assert digest["by_type"]["FILING_EVENT"] == 1
        assert digest["by_type"]["NEWS_ALERT"] == 1
        assert digest["by_type"]["INSTITUTIONAL_FLOW"] == 1
        assert digest["by_type"]["EARNINGS_CALENDAR"] == 2

        # Top alerts: should be all 10, HIGH first
        assert len(digest["top_alerts"]) == 10
        assert digest["top_alerts"][0]["severity"] == "HIGH"
        assert digest["top_alerts"][-1]["severity"] == "LOW"
