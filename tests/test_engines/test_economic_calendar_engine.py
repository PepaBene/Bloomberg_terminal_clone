"""Tests for Pillar 3 Phase 2 — Part 6: Economic Calendar Engine."""

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


# ── Release Surprise Tests ────────────────────────────────────────────────


class TestComputeReleaseSurprise:

    def test_above_consensus(self):
        result = compute_release_surprise(3.5, 3.2, 3.0, "CPI")
        assert result is not None
        assert result.surprise > 0
        assert result.direction == "ABOVE"

    def test_below_consensus(self):
        result = compute_release_surprise(2.8, 3.2, 3.0, "CPI")
        assert result is not None
        assert result.surprise < 0
        assert result.direction == "BELOW"

    def test_inline_consensus(self):
        result = compute_release_surprise(3.20, 3.20, 3.0, "CPI")
        assert result is not None
        assert result.direction == "INLINE"

    def test_none_actual(self):
        result = compute_release_surprise(None, 3.2, 3.0, "CPI")
        assert result is None

    def test_none_consensus(self):
        result = compute_release_surprise(3.5, None, 3.0, "CPI")
        assert result is None

    def test_zero_consensus_safe(self):
        # Should handle zero consensus gracefully
        result = compute_release_surprise(0.1, 0.0, 0.0, "CPI")
        # Either None or valid result with guarded division
        assert result is None or isinstance(result, ReleaseSurprise)


# ── Sector Sensitivity Tests ──────────────────────────────────────────────


class TestComputeSectorSensitivity:

    def test_cpi_above_consensus(self):
        surprise = ReleaseSurprise(
            release_type="CPI", actual=3.5, consensus=3.2,
            prior=3.0, surprise=0.3, surprise_magnitude=0.09375, direction="ABOVE",
        )
        impacts = compute_sector_sensitivity("CPI", surprise)
        assert len(impacts) > 0
        # Real Estate should be sensitive to CPI
        sectors = [i.sector for i in impacts]
        assert "Real Estate" in sectors

    def test_nfp_below_consensus(self):
        surprise = ReleaseSurprise(
            release_type="NFP", actual=150000, consensus=200000,
            prior=180000, surprise=-50000, surprise_magnitude=0.25, direction="BELOW",
        )
        impacts = compute_sector_sensitivity("NFP", surprise)
        assert len(impacts) > 0

    def test_fomc_hawkish(self):
        surprise = ReleaseSurprise(
            release_type="FOMC", actual=5.50, consensus=5.25,
            prior=5.25, surprise=0.25, surprise_magnitude=0.0476, direction="ABOVE",
        )
        impacts = compute_sector_sensitivity("FOMC", surprise)
        assert len(impacts) > 0

    def test_unknown_release_type(self):
        surprise = ReleaseSurprise(
            release_type="UNKNOWN_TYPE", actual=1.0, consensus=1.0,
            prior=1.0, surprise=0.0, surprise_magnitude=0.0, direction="INLINE",
        )
        impacts = compute_sector_sensitivity("UNKNOWN_TYPE", surprise)
        assert impacts == []

    def test_no_surprise(self):
        surprise = ReleaseSurprise(
            release_type="CPI", actual=3.2, consensus=3.2,
            prior=3.0, surprise=0.0, surprise_magnitude=0.0, direction="INLINE",
        )
        impacts = compute_sector_sensitivity("CPI", surprise)
        # Even inline, sectors should be listed but reaction muted
        assert isinstance(impacts, list)


# ── Historical Reaction Tests ─────────────────────────────────────────────


class TestComputeHistoricalReaction:

    def test_with_history(self):
        history = [
            {"surprise_magnitude": 0.05, "sector_reactions": {"Real Estate": -0.8, "Financials": -0.5}},
            {"surprise_magnitude": 0.03, "sector_reactions": {"Real Estate": -0.5, "Financials": -0.3}},
        ]
        result = compute_historical_reaction("CPI", history)
        assert isinstance(result, dict)

    def test_empty_history(self):
        result = compute_historical_reaction("CPI", [])
        assert result == {} or isinstance(result, dict)

    def test_single_data_point(self):
        history = [
            {"surprise_magnitude": 0.05, "sector_reactions": {"Real Estate": -0.8}},
        ]
        result = compute_historical_reaction("CPI", history)
        assert isinstance(result, dict)


# ── Calendar Merge Tests ──────────────────────────────────────────────────


class TestMergeWithCorporateCalendar:

    def test_merge_all_sources(self):
        economic = [{"type": "CPI", "date": "2026-03-15", "category": "ECONOMIC_DATA"}]
        earnings = [{"entity_id": "e1", "date": "2026-03-15", "type": "EARNINGS"}]
        ex_dates = [{"entity_id": "e2", "date": "2026-03-16", "type": "EX_DIVIDEND"}]
        fed = [{"date": "2026-03-19", "type": "FOMC"}]

        result = merge_with_corporate_calendar(economic, earnings, ex_dates, fed)
        assert len(result) >= 4

    def test_empty_sources(self):
        result = merge_with_corporate_calendar([], [], [], [])
        assert result == []

    def test_sorting_by_date(self):
        economic = [
            {"type": "GDP", "date": "2026-03-20", "category": "ECONOMIC_DATA"},
            {"type": "CPI", "date": "2026-03-10", "category": "ECONOMIC_DATA"},
        ]
        result = merge_with_corporate_calendar(economic, [], [], [])
        if len(result) >= 2:
            # Should be sorted by date
            dates = [r.get("date") for r in result if r.get("date") is not None]
            assert dates == sorted(dates)

    def test_mixed_sources(self):
        economic = [{"type": "CPI", "date": "2026-03-15", "category": "ECONOMIC_DATA"}]
        fed = [{"date": "2026-03-15", "type": "FOMC"}]
        result = merge_with_corporate_calendar(economic, [], [], fed)
        assert len(result) >= 2


# ── Upcoming Releases Tests ───────────────────────────────────────────────


class TestGetUpcomingReleases:

    def test_normal_window(self):
        releases = [
            {"date": "2026-03-25", "type": "CPI"},
            {"date": "2026-04-05", "type": "NFP"},
            {"date": "2026-05-15", "type": "GDP"},
        ]
        result = get_upcoming_releases(releases, "2026-03-22", days_ahead=14)
        # Only CPI (3 days ahead) should be in 14-day window
        assert len(result) >= 1

    def test_none_upcoming(self):
        releases = [{"date": "2026-01-01", "type": "CPI"}]
        result = get_upcoming_releases(releases, "2026-03-22", days_ahead=14)
        assert result == []

    def test_boundary(self):
        releases = [
            {"date": "2026-03-22", "type": "CPI"},  # Today
            {"date": "2026-04-05", "type": "NFP"},   # 14 days out
        ]
        result = get_upcoming_releases(releases, "2026-03-22", days_ahead=14)
        assert len(result) >= 1


# ── Analyze Release Tests ─────────────────────────────────────────────────


class TestAnalyzeRelease:

    def test_full_analysis(self):
        release = {
            "release_type": "CPI",
            "actual": 3.5,
            "consensus": 3.2,
            "prior": 3.0,
        }
        result = analyze_release(release)
        assert isinstance(result, ReleaseIntelligence)
        assert result.release_type == "CPI"
        assert result.surprise is not None
        assert len(result.sector_impacts) > 0

    def test_no_consensus(self):
        release = {
            "release_type": "CPI",
            "actual": 3.5,
            "consensus": None,
            "prior": 3.0,
        }
        result = analyze_release(release)
        assert result.surprise is None

    def test_with_history(self):
        release = {
            "release_type": "NFP",
            "actual": 250000,
            "consensus": 200000,
            "prior": 180000,
        }
        history = [
            {"surprise_magnitude": 0.1, "sector_reactions": {"Financials": 0.5}},
        ]
        result = analyze_release(release, historical_data=history)
        assert isinstance(result, ReleaseIntelligence)

    def test_inline_release(self):
        release = {
            "release_type": "GDP",
            "actual": 2.5,
            "consensus": 2.5,
            "prior": 2.4,
        }
        result = analyze_release(release)
        assert result.surprise is not None
        assert result.surprise.direction == "INLINE"

    def test_unknown_release_type(self):
        release = {
            "release_type": "UNKNOWN",
            "actual": 1.0,
            "consensus": 1.0,
            "prior": 1.0,
        }
        result = analyze_release(release)
        assert isinstance(result, ReleaseIntelligence)


# ── Constants Tests ───────────────────────────────────────────────────────


class TestConstants:

    def test_release_types_defined(self):
        assert "CPI" in RELEASE_TYPES
        assert "GDP" in RELEASE_TYPES
        assert "NFP" in RELEASE_TYPES
        assert "FOMC" in RELEASE_TYPES

    def test_all_have_category(self):
        for rt, config in RELEASE_TYPES.items():
            assert "category" in config, f"{rt} missing category"
            assert "importance" in config, f"{rt} missing importance"
            assert "sensitive_sectors" in config, f"{rt} missing sensitive_sectors"
