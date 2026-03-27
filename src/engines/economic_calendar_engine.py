"""Pillar 3 Phase 2 -- Part 6: Economic Calendar Engine.

Computes release surprises, sector sensitivity, historical reactions,
and merges economic events with corporate calendars.

All functions are pure computation -- no database access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Release type configuration
# ---------------------------------------------------------------------------

RELEASE_TYPES: dict[str, dict] = {
    "CPI": {
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "sensitive_sectors": ["Real Estate", "Utilities", "Consumer Discretionary"],
    },
    "CORE_CPI": {
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "sensitive_sectors": ["Real Estate", "Utilities"],
    },
    "GDP": {
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "sensitive_sectors": ["Industrials", "Financials", "Consumer Discretionary"],
    },
    "NFP": {
        "category": "ECONOMIC_DATA",
        "importance": "HIGH",
        "sensitive_sectors": ["Consumer Discretionary", "Financials"],
    },
    "UNEMPLOYMENT": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Consumer Discretionary"],
    },
    "RETAIL_SALES": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Consumer Discretionary", "Consumer Staples"],
    },
    "ISM_MFG": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Industrials", "Materials"],
    },
    "ISM_SVC": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Information Technology", "Communication Services"],
    },
    "HOUSING_STARTS": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Real Estate", "Materials"],
    },
    "PPI": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Materials", "Industrials"],
    },
    "FOMC": {
        "category": "CENTRAL_BANK",
        "importance": "HIGH",
        "sensitive_sectors": ["Financials", "Real Estate", "Utilities"],
    },
    "ECB": {
        "category": "CENTRAL_BANK",
        "importance": "HIGH",
        "sensitive_sectors": ["Financials"],
    },
    "BOJ": {
        "category": "CENTRAL_BANK",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Financials"],
    },
    "TREASURY_AUCTION": {
        "category": "TREASURY",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Financials"],
    },
    "DURABLE_GOODS": {
        "category": "ECONOMIC_DATA",
        "importance": "MEDIUM",
        "sensitive_sectors": ["Industrials"],
    },
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ReleaseSurprise:
    """Surprise vs consensus for an economic release."""
    release_type: str
    actual: float
    consensus: float
    prior: float | None
    surprise: float
    surprise_magnitude: float
    direction: str  # ABOVE / BELOW / INLINE


@dataclass
class SectorImpact:
    """Expected sector-level impact from a release surprise."""
    sector: str
    sensitivity: float
    expected_reaction: str
    historical_avg_reaction_pct: float | None


@dataclass
class ReleaseIntelligence:
    """Full intelligence for a single economic release."""
    release_type: str
    release_category: str
    surprise: ReleaseSurprise | None
    sector_impacts: list
    importance: str
    ai_summary: str | None = None


# ---------------------------------------------------------------------------
# 1. Compute release surprise
# ---------------------------------------------------------------------------

def compute_release_surprise(
    actual: float | None,
    consensus: float | None,
    prior: float | None,
    release_type: str,
) -> ReleaseSurprise | None:
    """Compute the surprise between actual and consensus values.

    Parameters
    ----------
    actual : Actual released value.
    consensus : Market consensus estimate.
    prior : Prior period value (for context).
    release_type : Economic release type key.

    Returns
    -------
    ReleaseSurprise or None if actual or consensus is missing.
    """
    if actual is None or consensus is None:
        return None

    surprise = actual - consensus

    # Magnitude relative to consensus (avoid division by zero)
    if consensus != 0:
        surprise_magnitude = abs(surprise / consensus)
    else:
        surprise_magnitude = abs(surprise)

    # Determine direction
    threshold = 0.001 * (abs(consensus) if consensus != 0 else 1.0)
    if surprise > threshold:
        direction = "ABOVE"
    elif surprise < -threshold:
        direction = "BELOW"
    else:
        direction = "INLINE"

    return ReleaseSurprise(
        release_type=release_type,
        actual=actual,
        consensus=consensus,
        prior=prior,
        surprise=round(surprise, 4),
        surprise_magnitude=round(surprise_magnitude, 4),
        direction=direction,
    )


# ---------------------------------------------------------------------------
# 2. Compute sector sensitivity
# ---------------------------------------------------------------------------

def compute_sector_sensitivity(
    release_type: str,
    surprise: ReleaseSurprise | None,
) -> list[SectorImpact]:
    """Determine which sectors are sensitive to a given release.

    Parameters
    ----------
    release_type : Release type key (e.g. 'CPI', 'FOMC').
    surprise : Optional surprise data (used for direction).

    Returns
    -------
    list[SectorImpact] for each sensitive sector.
    """
    config = RELEASE_TYPES.get(release_type)
    if config is None:
        return []

    sensitive = config.get("sensitive_sectors", [])
    if not sensitive:
        return []

    impacts: list[SectorImpact] = []
    base_sensitivity = 1.0 if config.get("importance") == "HIGH" else 0.7

    for i, sector in enumerate(sensitive):
        # First-listed sector is most sensitive, decay slightly
        sensitivity = round(base_sensitivity * (1.0 - 0.1 * i), 4)
        sensitivity = max(sensitivity, 0.3)

        # Determine expected reaction direction
        if surprise is not None:
            if surprise.direction == "ABOVE":
                expected = "POSITIVE"
            elif surprise.direction == "BELOW":
                expected = "NEGATIVE"
            else:
                expected = "NEUTRAL"
        else:
            expected = "NEUTRAL"

        impacts.append(SectorImpact(
            sector=sector,
            sensitivity=sensitivity,
            expected_reaction=expected,
            historical_avg_reaction_pct=None,
        ))

    return impacts


# ---------------------------------------------------------------------------
# 3. Compute historical reaction
# ---------------------------------------------------------------------------

def compute_historical_reaction(
    release_type: str,
    historical_data: list[dict],
) -> dict[str, float]:
    """Compute average sector reaction per unit surprise from history.

    Parameters
    ----------
    release_type : Release type key.
    historical_data : list of dicts with keys:
        surprise (float), sector_reactions ({sector: pct_change}).

    Returns
    -------
    {sector: avg_reaction_per_unit_surprise}
    """
    if not historical_data:
        return {}

    sector_reactions: dict[str, list[float]] = {}

    for entry in historical_data:
        surprise = entry.get("surprise", 0.0)
        if surprise == 0:
            continue
        reactions = entry.get("sector_reactions", {})
        for sector, pct_change in reactions.items():
            if sector not in sector_reactions:
                sector_reactions[sector] = []
            # Reaction per unit surprise
            sector_reactions[sector].append(pct_change / surprise)

    result: dict[str, float] = {}
    for sector, vals in sector_reactions.items():
        if vals:
            result[sector] = round(sum(vals) / len(vals), 4)

    return result


# ---------------------------------------------------------------------------
# 4. Merge with corporate calendar
# ---------------------------------------------------------------------------

def merge_with_corporate_calendar(
    economic_events: list[dict],
    earnings_dates: list[dict],
    ex_dates: list[dict],
    fed_meetings: list[dict],
) -> list[dict]:
    """Merge economic releases with corporate calendar into unified timeline.

    Parameters
    ----------
    economic_events : [{date, release_type, ...}]
    earnings_dates : [{date, entity_id, entity_name, ...}]
    ex_dates : [{date, entity_id, entity_name, type, ...}]
    fed_meetings : [{date, meeting_type, ...}]

    Returns
    -------
    list[dict] sorted by date ascending. Each has:
        event_date, event_type, source, title, importance, entity_id (optional).
    """
    unified: list[dict] = []

    for evt in economic_events:
        evt_date = _parse_date(evt.get("date"))
        if evt_date is None:
            continue
        rtype = evt.get("release_type", "UNKNOWN")
        config = RELEASE_TYPES.get(rtype, {})
        unified.append({
            "event_date": evt_date,
            "event_type": "ECONOMIC_RELEASE",
            "source": "economic",
            "title": evt.get("title", rtype),
            "importance": config.get("importance", "MEDIUM"),
            "entity_id": None,
            "release_type": rtype,
        })

    for evt in earnings_dates:
        evt_date = _parse_date(evt.get("date"))
        if evt_date is None:
            continue
        unified.append({
            "event_date": evt_date,
            "event_type": "EARNINGS",
            "source": "corporate",
            "title": evt.get("title", f"{evt.get('entity_name', '')} Earnings"),
            "importance": "HIGH",
            "entity_id": evt.get("entity_id"),
        })

    for evt in ex_dates:
        evt_date = _parse_date(evt.get("date"))
        if evt_date is None:
            continue
        unified.append({
            "event_date": evt_date,
            "event_type": evt.get("type", "EX_DATE"),
            "source": "corporate",
            "title": evt.get("title", f"{evt.get('entity_name', '')} Ex-Date"),
            "importance": "MEDIUM",
            "entity_id": evt.get("entity_id"),
        })

    for evt in fed_meetings:
        evt_date = _parse_date(evt.get("date"))
        if evt_date is None:
            continue
        unified.append({
            "event_date": evt_date,
            "event_type": "FED_MEETING",
            "source": "central_bank",
            "title": evt.get("title", evt.get("meeting_type", "Fed Meeting")),
            "importance": "HIGH",
            "entity_id": None,
        })

    # Sort by date ascending
    unified.sort(key=lambda e: e["event_date"])
    return unified


def _parse_date(value) -> date | None:
    """Parse a date from string or date object."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# 5. Get upcoming releases
# ---------------------------------------------------------------------------

def get_upcoming_releases(
    all_releases: list[dict],
    reference_date: str,
    days_ahead: int = 14,
) -> list[dict]:
    """Filter releases to those within days_ahead of reference_date.

    Parameters
    ----------
    all_releases : list[dict]
        Each: {date, release_type, ...}.
    reference_date : str
        ISO date string for the reference point.
    days_ahead : int
        Number of days to look ahead.

    Returns
    -------
    list[dict] of upcoming releases sorted by date.
    """
    ref = _parse_date(reference_date)
    if ref is None:
        return []

    end = ref + timedelta(days=days_ahead)
    result: list[dict] = []

    for release in all_releases:
        rel_date = _parse_date(release.get("date"))
        if rel_date is None:
            continue
        if ref <= rel_date <= end:
            result.append(release)

    result.sort(key=lambda r: _parse_date(r.get("date")) or ref)
    return result


# ---------------------------------------------------------------------------
# 6. Analyze release (orchestrator)
# ---------------------------------------------------------------------------

def analyze_release(
    release_data: dict,
    historical_data: list[dict] | None = None,
) -> ReleaseIntelligence:
    """Full analysis of an economic release.

    Parameters
    ----------
    release_data : dict
        Keys: release_type, actual (optional), consensus (optional),
        prior (optional).
    historical_data : list[dict] | None
        Optional historical reaction data for enrichment.

    Returns
    -------
    ReleaseIntelligence with surprise, sector impacts, and importance.
    """
    release_type = release_data.get("release_type", "UNKNOWN")
    config = RELEASE_TYPES.get(release_type, {})
    category = config.get("category", "UNKNOWN")
    importance = config.get("importance", "MEDIUM")

    # Compute surprise
    surprise = compute_release_surprise(
        actual=release_data.get("actual"),
        consensus=release_data.get("consensus"),
        prior=release_data.get("prior"),
        release_type=release_type,
    )

    # Compute sector sensitivity
    sector_impacts = compute_sector_sensitivity(release_type, surprise)

    # Enrich with historical data if available
    if historical_data and sector_impacts:
        hist_reactions = compute_historical_reaction(release_type, historical_data)
        for impact in sector_impacts:
            avg_reaction = hist_reactions.get(impact.sector)
            if avg_reaction is not None:
                impact.historical_avg_reaction_pct = round(avg_reaction, 4)

    return ReleaseIntelligence(
        release_type=release_type,
        release_category=category,
        surprise=surprise,
        sector_impacts=sector_impacts,
        importance=importance,
    )
