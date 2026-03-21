"""Events Calendar Engine.

Provides unified event aggregation and sorting.
All functions are pure computation — no database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class UnifiedEvent:
    """A normalized event from any source."""
    event_id: str
    source_type: str
    event_date: date
    title: str
    description: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    importance: str | None = None


def get_unified_events(
    events_by_source: dict[str, list[dict]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[UnifiedEvent]:
    """Merge events from multiple sources into a single sorted list.

    Parameters
    ----------
    events_by_source : {source_type: [{event_date, title, ...}]}
    start_date : Optional start filter.
    end_date : Optional end filter.

    Returns
    -------
    List of UnifiedEvent sorted by event_date ascending.
    """
    all_events = []

    for source_type, events in events_by_source.items():
        for i, evt in enumerate(events):
            evt_date = evt.get("event_date")
            if isinstance(evt_date, str):
                try:
                    evt_date = date.fromisoformat(evt_date)
                except ValueError:
                    continue
            elif not isinstance(evt_date, date):
                continue

            if start_date and evt_date < start_date:
                continue
            if end_date and evt_date > end_date:
                continue

            all_events.append(UnifiedEvent(
                event_id=evt.get("event_id", f"{source_type}-{i}"),
                source_type=source_type,
                event_date=evt_date,
                title=evt.get("title", ""),
                description=evt.get("description"),
                entity_id=evt.get("entity_id"),
                entity_name=evt.get("entity_name"),
                importance=evt.get("importance", "MEDIUM"),
            ))

    all_events.sort(key=lambda e: e.event_date)
    return all_events


def summarize_events(events: list[UnifiedEvent]) -> dict:
    """Summarize events by source type.

    Returns {total_events, by_source: {source_type: count}}.
    """
    by_source: dict[str, int] = {}
    for evt in events:
        by_source[evt.source_type] = by_source.get(evt.source_type, 0) + 1

    return {
        "total_events": len(events),
        "by_source": by_source,
    }
