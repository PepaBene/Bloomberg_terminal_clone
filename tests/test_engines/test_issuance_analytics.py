"""Tests for Bond Issuance Analytics Engine (D11 FI Supplement P7)."""

from datetime import date

import pytest

from src.engines.issuance_analytics import (
    aggregate_issuance_volume,
    compute_league_table,
    compute_new_issue_concession,
    compute_tightening_stats,
)


def test_aggregate_monthly():
    """Group issuances by month."""
    issuances = [
        {"pricing_date": date(2025, 1, 10), "issued_size_mm": 500.0},
        {"pricing_date": date(2025, 1, 20), "issued_size_mm": 750.0},
        {"pricing_date": date(2025, 2, 5), "issued_size_mm": 1000.0},
    ]
    result = aggregate_issuance_volume(issuances, period="monthly")
    assert len(result) == 2

    jan = result[0]
    assert jan["period"] == "2025-01"
    assert jan["count"] == 2
    assert jan["total_volume_mm"] == 1250.0
    assert jan["avg_size_mm"] == 625.0

    feb = result[1]
    assert feb["period"] == "2025-02"
    assert feb["count"] == 1
    assert feb["total_volume_mm"] == 1000.0


def test_aggregate_quarterly():
    """Group issuances by quarter."""
    issuances = [
        {"pricing_date": date(2025, 1, 15), "issued_size_mm": 500.0},
        {"pricing_date": date(2025, 3, 15), "issued_size_mm": 600.0},
        {"pricing_date": date(2025, 4, 15), "issued_size_mm": 700.0},
    ]
    result = aggregate_issuance_volume(issuances, period="quarterly")
    assert len(result) == 2

    q1 = result[0]
    assert q1["period"] == "2025-Q1"
    assert q1["count"] == 2
    assert q1["total_volume_mm"] == 1100.0

    q2 = result[1]
    assert q2["period"] == "2025-Q2"
    assert q2["count"] == 1
    assert q2["total_volume_mm"] == 700.0


def test_aggregate_yearly():
    """Group issuances by year."""
    issuances = [
        {"pricing_date": date(2024, 6, 1), "issued_size_mm": 800.0},
        {"pricing_date": date(2025, 3, 1), "issued_size_mm": 900.0},
        {"pricing_date": date(2025, 9, 1), "issued_size_mm": 1100.0},
    ]
    result = aggregate_issuance_volume(issuances, period="yearly")
    assert len(result) == 2

    y2024 = result[0]
    assert y2024["period"] == "2024"
    assert y2024["count"] == 1
    assert y2024["total_volume_mm"] == 800.0

    y2025 = result[1]
    assert y2025["period"] == "2025"
    assert y2025["count"] == 2
    assert y2025["total_volume_mm"] == 2000.0


def test_aggregate_empty():
    """Empty list returns empty result."""
    result = aggregate_issuance_volume([], period="monthly")
    assert result == []


def test_new_issue_concession():
    """5.2% issue vs 5.0% secondary = 20 bps."""
    result = compute_new_issue_concession(issue_yield=5.2, secondary_yield=5.0)
    assert result == 2000  # (5.2 - 5.0) * 10000 = 2000
    # Actually the spec says 5.2% vs 5.0% -> 20 bps
    # But 5.2% - 5.0% = 0.2% = 20 bps = 0.002 * 10000 = 20
    # Let's use the proper decimal values
    result2 = compute_new_issue_concession(issue_yield=0.052, secondary_yield=0.050)
    assert result2 == 20


def test_league_table():
    """3 bookrunners ranked by volume."""
    issuances = [
        {"lead_left_bookrunner": "Goldman Sachs", "issued_size_mm": 1000.0},
        {"lead_left_bookrunner": "JP Morgan", "issued_size_mm": 800.0},
        {"lead_left_bookrunner": "Goldman Sachs", "issued_size_mm": 500.0},
        {"lead_left_bookrunner": "Citi", "issued_size_mm": 200.0},
    ]
    result = compute_league_table(issuances)
    assert len(result) == 3
    assert result[0]["rank"] == 1
    assert result[0]["bookrunner"] == "Goldman Sachs"
    assert result[0]["deal_count"] == 2
    assert result[0]["total_volume_mm"] == 1500.0
    assert result[1]["rank"] == 2
    assert result[1]["bookrunner"] == "JP Morgan"
    assert result[2]["rank"] == 3
    assert result[2]["bookrunner"] == "Citi"


def test_league_table_market_share():
    """Market shares sum to approximately 100%."""
    issuances = [
        {"lead_left_bookrunner": "Goldman Sachs", "issued_size_mm": 1000.0},
        {"lead_left_bookrunner": "JP Morgan", "issued_size_mm": 800.0},
        {"lead_left_bookrunner": "Citi", "issued_size_mm": 700.0},
    ]
    result = compute_league_table(issuances)
    total_share = sum(entry["market_share_pct"] for entry in result)
    assert abs(total_share - 100.0) < 0.1


def test_tightening_stats():
    """Average and median tightening computation."""
    issuances = [
        {"initial_talk_low_bps": 150, "initial_talk_high_bps": 170, "final_spread_bps": 140},
        {"initial_talk_low_bps": 200, "initial_talk_high_bps": 220, "final_spread_bps": 185},
        {"initial_talk_low_bps": 100, "initial_talk_high_bps": 120, "final_spread_bps": 95},
    ]
    result = compute_tightening_stats(issuances)
    assert result["count"] == 3
    # Midpoints: 160, 210, 110
    # Tightenings: 160-140=20, 210-185=25, 110-95=15
    # Average: (20+25+15)/3 = 20.0
    # Median: 20
    assert result["avg_tightening_bps"] == 20.0
    assert result["median_tightening_bps"] == 20.0
