"""Pure-Python security search engine (Pillar 2 Supplement Part 5).

The HTTP layer in ``src/api/routers/security_finder.py`` runs against the
database. This engine module exposes the same name/ticker matching logic
as plain functions over a pre-loaded list of securities so it can be unit
tested without a database — and so screening / batch jobs can call the
same scoring code as the API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SecuritySearchResult:
    """Lightweight search result returned by ``search_securities``."""

    security_id: str
    name: str
    short_name: str | None
    security_type: str
    asset_class: str | None
    status: str | None
    relevance_score: float


def _relevance(name: str | None, short_name: str | None, query: str) -> float:
    """Heuristic 0..1 relevance score.

    Exact matches on name or short_name (ticker) score 1.0; prefix
    matches 0.85; substring matches 0.6.
    """
    if not query:
        return 0.0
    q = query.lower().strip()
    n = (name or "").lower()
    s = (short_name or "").lower()
    if q == s:
        return 1.0
    if q == n:
        return 0.95
    if s and s.startswith(q):
        return 0.9
    if n.startswith(q):
        return 0.85
    if s and q in s:
        return 0.7
    if q in n:
        return 0.6
    return 0.0


def search_securities(
    query: str,
    securities: list[dict],
    security_type: str | None = None,
    asset_class: str | None = None,
    max_results: int = 50,
    include_inactive: bool = False,
) -> list[SecuritySearchResult]:
    """Filter and score ``securities`` against ``query``.

    Each ``securities`` entry is a dict with keys ``security_id``,
    ``name``, ``short_name``, ``security_type``, ``asset_class``, and
    ``status``. Results are sorted by relevance descending. Inactive
    securities are dropped by default.
    """
    if not query or not query.strip():
        return []

    results: list[SecuritySearchResult] = []
    for sec in securities:
        if not include_inactive and (sec.get("status") or "").upper() == "INACTIVE":
            continue
        if security_type and (sec.get("security_type") or "").upper() != security_type.upper():
            continue
        if asset_class and (sec.get("asset_class") or "").upper() != asset_class.upper():
            continue
        score = _relevance(sec.get("name"), sec.get("short_name"), query)
        if score == 0.0:
            continue
        results.append(SecuritySearchResult(
            security_id=str(sec.get("security_id", "")),
            name=sec.get("name", ""),
            short_name=sec.get("short_name"),
            security_type=sec.get("security_type", ""),
            asset_class=sec.get("asset_class"),
            status=sec.get("status"),
            relevance_score=score,
        ))

    results.sort(key=lambda r: -r.relevance_score)
    return results[:max_results]


def suggest_securities(
    query: str,
    securities: list[dict],
    max_suggestions: int = 10,
) -> list[dict]:
    """Return autocomplete suggestions of the form
    ``{"security_id", "display", "security_type"}``.

    ``display`` combines the ticker (if available) with the legal name,
    e.g. "AAPL — Apple Inc.".
    """
    if not query or not query.strip():
        return []

    matches = search_securities(query, securities, max_results=max_suggestions)
    out: list[dict] = []
    for m in matches:
        if m.short_name:
            display = f"{m.short_name} — {m.name}"
        else:
            display = m.name
        out.append({
            "security_id": m.security_id,
            "display": display,
            "security_type": m.security_type,
        })
    return out[:max_suggestions]
