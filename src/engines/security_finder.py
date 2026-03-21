"""Security Finder Engine.

Provides text-based search and relevance scoring over securities.
All functions are pure computation — no database access.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Single search result with relevance score."""
    security_id: str
    name: str
    short_name: str | None
    security_type: str
    asset_class: str | None
    status: str | None
    relevance_score: float


def search_securities(
    query: str,
    securities: list[dict],
    max_results: int = 20,
    security_type: str | None = None,
    asset_class: str | None = None,
    status: str | None = None,
) -> list[SearchResult]:
    """Search securities by name/short_name with relevance scoring.

    Parameters
    ----------
    query : Search query string.
    securities : list of dicts with keys: security_id, name, short_name,
                 security_type, asset_class, status.
    max_results : Maximum results to return.
    security_type : Filter by security type.
    asset_class : Filter by asset class.
    status : Filter by status.

    Returns
    -------
    list of SearchResult sorted by relevance descending.
    """
    if not query or not securities:
        return []

    query_lower = query.lower().strip()
    results = []

    for sec in securities:
        # Apply filters
        if security_type and sec.get("security_type", "").upper() != security_type.upper():
            continue
        if asset_class and sec.get("asset_class", "").upper() != asset_class.upper():
            continue
        if status and sec.get("status", "").upper() != status.upper():
            continue

        # Score relevance
        score = _compute_relevance(query_lower, sec)
        if score > 0:
            results.append(SearchResult(
                security_id=str(sec.get("security_id", "")),
                name=sec.get("name", ""),
                short_name=sec.get("short_name"),
                security_type=sec.get("security_type", ""),
                asset_class=sec.get("asset_class"),
                status=sec.get("status"),
                relevance_score=round(score, 4),
            ))

    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results[:max_results]


def _compute_relevance(query: str, sec: dict) -> float:
    """Score relevance of a security to a query string."""
    score = 0.0
    name = (sec.get("name") or "").lower()
    short_name = (sec.get("short_name") or "").lower()

    # Exact match on short_name (ticker)
    if short_name == query:
        score += 100.0
    elif short_name.startswith(query):
        score += 80.0
    elif query in short_name:
        score += 50.0

    # Name matching
    if name == query:
        score += 90.0
    elif name.startswith(query):
        score += 60.0
    elif query in name:
        score += 30.0

    # Word matching
    query_words = query.split()
    name_words = name.split()
    for qw in query_words:
        for nw in name_words:
            if nw.startswith(qw):
                score += 10.0

    return score


def suggest_securities(
    query: str,
    securities: list[dict],
    max_suggestions: int = 10,
) -> list[dict]:
    """Return autocomplete suggestions.

    Returns list of {security_id, display, security_type}.
    """
    results = search_securities(query, securities, max_results=max_suggestions)
    suggestions = []
    for r in results:
        display = r.short_name or r.name
        if r.short_name and r.name:
            display = f"{r.short_name} - {r.name}"
        suggestions.append({
            "security_id": r.security_id,
            "display": display,
            "security_type": r.security_type,
        })
    return suggestions
