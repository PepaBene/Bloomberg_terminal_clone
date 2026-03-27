"""Tests for the economic calendar engine (Pillar 3 Phase 2 -- Part 6)."""

from datetime import date

import pytest

from src.engines.economic_calendar_engine import (
    RELEASE_TYPES,
    ReleaseSurprise,
    SectorImpact,
    ReleaseIntelligence,
    compute_release_surprise,
    compute_sector_sensitivity,
    compute_historical_reaction,
    merge_with_corporate_calendar,
    get_upcoming_releases,
    analyze_release,
)


# ═══════════════════════════════════════════════════════════════════════════
# TestReleaseSurprise
# ═══════════════════════════════════════════════════════════════════════════


class TestReleaseSurprise:
    def test_beat_consensus(self):
        result = compute_release_surprise(actual=3.5, consensus=3.2, prior=3.0, release_type="CPI")
        assert result is not None
        assert result.direction == "ABOVE"
        assert result.surprise > 0
        assert result.surprise_magnitude > 0

    def test_miss_consensus(self):
        result = compute_release_surprise(actual=2.8, consensus=3.2, prior=3.0, release_type="CPI")
        assert result is not None
        assert result.direction == "BELOW"
        assert result.surprise < 0

    def test_inline_consensus(self):
        result = compute_release_surprise(actual=3.200, consensus=3.200, prior=3.0, release_type="GDP")
        assert result is not None
        assert result.direction == "INLINE"

    def test_none_actual(self):
        result = compute_release_surprise(actual=None, consensus=3.2, prior=3.0, release_type="CPI")
        assert result is None

    def test_zero_consensus(self):
        result = compute_release_surprise(actual=0.5, consensus=0.0, prior=-0.1, release_type="GDP")
        assert result is not None
        assert result.direction == "ABOVE"
        assert result.surprise == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# TestSectorSensitivity
# ═══════════════════════════════════════════════════════════════════════════


class TestSectorSensitivity:
    def test_cpi_above(self):
        surprise = ReleaseSurprise("CPI", 3.5, 3.2, 3.0, 0.3, 0.0938, "ABOVE")
        impacts = compute_sector_sensitivity("CPI", surprise)
        assert len(impacts) == 3  # Real Estate, Utilities, Consumer Discretionary
        assert impacts[0].sector == "Real Estate"
        assert impacts[0].expected_reaction == "POSITIVE"
        assert impacts[0].sensitivity > impacts[-1].sensitivity

    def test_nfp_below(self):
        surprise = ReleaseSurprise("NFP", 150, 200, 190, -50, 0.25, "BELOW")
        impacts = compute_sector_sensitivity("NFP", surprise)
        assert len(impacts) == 2  # Consumer Discretionary, Financials
        for imp in impacts:
            assert imp.expected_reaction == "NEGATIVE"

    def test_fomc_no_surprise(self):
        impacts = compute_sector_sensitivity("FOMC", None)
        assert len(impacts) == 3
        for imp in impacts:
            assert imp.expected_reaction == "NEUTRAL"

    def test_unknown_release_type(self):
        impacts = compute_sector_sensitivity("UNKNOWN_TYPE", None)
        assert impacts == []

    def test_empty_no_sectors(self):
        """BOJ has only Financials."""
        impacts = compute_sector_sensitivity("BOJ", None)
        assert len(impacts) == 1
        assert impacts[0].sector == "Financials"


# ═══════════════════════════════════════════════════════════════════════════
# TestHistoricalReaction
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoricalReaction:
    def test_normal_history(self):
        historical = [
            {"surprise": 0.3, "sector_reactions": {"Real Estate": -0.6, "Utilities": -0.3}},
            {"surprise": -0.2, "sector_reactions": {"Real Estate": 0.4, "Utilities": 0.2}},
        ]
        result = compute_historical_reaction("CPI", historical)
        assert "Real Estate" in result
        assert "Utilities" in result

    def test_no_history(self):
        result = compute_historical_reaction("CPI", [])
        assert result == {}

    def test_single_entry(self):
        historical = [
            {"surprise": 0.5, "sector_reactions": {"Financials": 1.0}},
        ]
        result = compute_historical_reaction("NFP", historical)
        assert "Financials" in result
        assert result["Financials"] == pytest.approx(2.0, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TestMergeCorporateCalendar
# ═══════════════════════════════════════════════════════════════════════════


class TestMergeCorporateCalendar:
    def test_all_sources(self):
        economic = [{"date": "2024-07-10", "release_type": "CPI", "title": "CPI Release"}]
        earnings = [{"date": "2024-07-15", "entity_id": "E1", "entity_name": "Apple", "title": "AAPL Earnings"}]
        ex_dates = [{"date": "2024-07-12", "entity_id": "E2", "entity_name": "MSFT", "type": "EX_DIVIDEND"}]
        fed = [{"date": "2024-07-31", "meeting_type": "FOMC", "title": "FOMC Decision"}]

        merged = merge_with_corporate_calendar(economic, earnings, ex_dates, fed)
        assert len(merged) == 4
        assert merged[0]["event_date"] == date(2024, 7, 10)
        assert merged[-1]["event_date"] == date(2024, 7, 31)

    def test_empty_all_sources(self):
        merged = merge_with_corporate_calendar([], [], [], [])
        assert merged == []

    def test_date_filter_sort(self):
        economic = [
            {"date": "2024-07-20", "release_type": "GDP"},
            {"date": "2024-07-05", "release_type": "NFP"},
        ]
        merged = merge_with_corporate_calendar(economic, [], [], [])
        assert len(merged) == 2
        assert merged[0]["event_date"] < merged[1]["event_date"]

    def test_sort_mixed_dates(self):
        economic = [{"date": "2024-08-01", "release_type": "CPI"}]
        earnings = [{"date": "2024-07-01", "entity_id": "E1", "entity_name": "Co"}]
        merged = merge_with_corporate_calendar(economic, earnings, [], [])
        assert merged[0]["event_type"] == "EARNINGS"
        assert merged[1]["event_type"] == "ECONOMIC_RELEASE"


# ═══════════════════════════════════════════════════════════════════════════
# TestUpcomingReleases
# ═══════════════════════════════════════════════════════════════════════════


class TestUpcomingReleases:
    def test_normal_window(self):
        releases = [
            {"date": "2024-07-10", "release_type": "CPI"},
            {"date": "2024-07-15", "release_type": "NFP"},
            {"date": "2024-08-01", "release_type": "GDP"},
        ]
        upcoming = get_upcoming_releases(releases, "2024-07-08", days_ahead=14)
        assert len(upcoming) == 2

    def test_none_in_window(self):
        releases = [
            {"date": "2024-09-01", "release_type": "CPI"},
        ]
        upcoming = get_upcoming_releases(releases, "2024-07-08", days_ahead=14)
        assert upcoming == []

    def test_boundary_dates(self):
        releases = [
            {"date": "2024-07-08", "release_type": "CPI"},  # Exact start
            {"date": "2024-07-22", "release_type": "NFP"},  # Exact end
            {"date": "2024-07-23", "release_type": "GDP"},  # One day past
        ]
        upcoming = get_upcoming_releases(releases, "2024-07-08", days_ahead=14)
        assert len(upcoming) == 2


# ═══════════════════════════════════════════════════════════════════════════
# TestAnalyzeRelease
# ═══════════════════════════════════════════════════════════════════════════


class TestAnalyzeRelease:
    def test_full_analysis(self):
        release = {"release_type": "CPI", "actual": 3.5, "consensus": 3.2, "prior": 3.0}
        result = analyze_release(release)
        assert isinstance(result, ReleaseIntelligence)
        assert result.release_type == "CPI"
        assert result.release_category == "ECONOMIC_DATA"
        assert result.importance == "HIGH"
        assert result.surprise is not None
        assert result.surprise.direction == "ABOVE"
        assert len(result.sector_impacts) == 3

    def test_no_consensus(self):
        release = {"release_type": "GDP", "actual": 2.5}
        result = analyze_release(release)
        assert result.surprise is None
        # Sector impacts still computed, just with no surprise direction
        assert len(result.sector_impacts) > 0

    def test_with_history(self):
        release = {"release_type": "CPI", "actual": 3.5, "consensus": 3.2, "prior": 3.0}
        history = [
            {"surprise": 0.3, "sector_reactions": {"Real Estate": -0.9, "Utilities": -0.3}},
        ]
        result = analyze_release(release, historical_data=history)
        assert result.surprise is not None
        # Historical enrichment should populate at least one sector
        has_hist = any(
            imp.historical_avg_reaction_pct is not None
            for imp in result.sector_impacts
        )
        assert has_hist is True

    def test_no_surprise_when_missing_actual(self):
        release = {"release_type": "FOMC"}
        result = analyze_release(release)
        assert result.surprise is None
        assert result.importance == "HIGH"

    def test_edge_unknown_release_type(self):
        release = {"release_type": "UNKNOWN_XYZ", "actual": 1.0, "consensus": 1.5}
        result = analyze_release(release)
        assert result.release_category == "UNKNOWN"
        assert result.sector_impacts == []
        assert result.surprise is not None
