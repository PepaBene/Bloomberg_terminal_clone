"""Tests for the events calendar engine (Pillar 2 Supplement – Part 5)."""

from datetime import date

import pytest

from src.engines.events_calendar import get_unified_events, summarize_events


SAMPLE_EVENTS = {
    "EARNINGS_ANNOUNCEMENT": [
        {"event_id": "ea1", "event_date": date(2024, 7, 25), "title": "AAPL Q3 Earnings", "importance": "HIGH"},
        {"event_id": "ea2", "event_date": date(2024, 7, 30), "title": "MSFT Q4 Earnings", "importance": "HIGH"},
    ],
    "FED_MEETING": [
        {"event_id": "fm1", "event_date": date(2024, 7, 31), "title": "FOMC Decision", "importance": "HIGH"},
    ],
    "CORPORATE_ACTION": [
        {"event_id": "ca1", "event_date": date(2024, 7, 20), "title": "GOOG Stock Split", "importance": "MEDIUM"},
    ],
}


class TestUnifiedEvents:
    def test_merge_all_sources(self):
        events = get_unified_events(SAMPLE_EVENTS)
        assert len(events) == 4

    def test_sorted_by_date(self):
        events = get_unified_events(SAMPLE_EVENTS)
        dates = [e.event_date for e in events]
        assert dates == sorted(dates)

    def test_date_filter(self):
        events = get_unified_events(
            SAMPLE_EVENTS,
            start_date=date(2024, 7, 25),
            end_date=date(2024, 7, 30),
        )
        assert len(events) == 2

    def test_empty_sources(self):
        events = get_unified_events({})
        assert events == []

    def test_string_dates(self):
        events_with_str = {
            "TEST": [
                {"event_date": "2024-07-15", "title": "Test Event"},
            ],
        }
        events = get_unified_events(events_with_str)
        assert len(events) == 1
        assert events[0].event_date == date(2024, 7, 15)


class TestSummarizeEvents:
    def test_basic_summary(self):
        events = get_unified_events(SAMPLE_EVENTS)
        summary = summarize_events(events)
        assert summary["total_events"] == 4
        assert summary["by_source"]["EARNINGS_ANNOUNCEMENT"] == 2
        assert summary["by_source"]["FED_MEETING"] == 1
        assert summary["by_source"]["CORPORATE_ACTION"] == 1

    def test_empty_summary(self):
        summary = summarize_events([])
        assert summary["total_events"] == 0
        assert summary["by_source"] == {}
