"""D11 FI Supplement P7: Bond Issuance Analytics Engine.

Pure computation functions (no DB access) for bond issuance analysis.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median


def aggregate_issuance_volume(
    issuances: list[dict], period: str = "monthly"
) -> list[dict]:
    """Aggregate issuance volume by period (monthly/quarterly/yearly).

    Each issuance dict has 'pricing_date' and 'issued_size_mm'.
    Returns list of dicts: {period, count, total_volume_mm, avg_size_mm}.
    """
    if not issuances:
        return []

    buckets: dict[str, list[float]] = defaultdict(list)

    for iss in issuances:
        pricing_date = iss.get("pricing_date")
        size = iss.get("issued_size_mm")
        if pricing_date is None or size is None:
            continue

        if isinstance(pricing_date, str):
            pricing_date = date.fromisoformat(pricing_date)

        if period == "monthly":
            key = f"{pricing_date.year}-{pricing_date.month:02d}"
        elif period == "quarterly":
            q = (pricing_date.month - 1) // 3 + 1
            key = f"{pricing_date.year}-Q{q}"
        elif period == "yearly":
            key = str(pricing_date.year)
        else:
            key = f"{pricing_date.year}-{pricing_date.month:02d}"

        buckets[key].append(float(size))

    result = []
    for bucket_key in sorted(buckets.keys()):
        sizes = buckets[bucket_key]
        total = sum(sizes)
        count = len(sizes)
        result.append({
            "period": bucket_key,
            "count": count,
            "total_volume_mm": round(total, 2),
            "avg_size_mm": round(total / count, 2) if count > 0 else 0.0,
        })

    return result


def compute_new_issue_concession(
    issue_yield: float, secondary_yield: float
) -> float:
    """New issue concession in basis points."""
    return round((issue_yield - secondary_yield) * 10000)


def compute_league_table(issuances: list[dict]) -> list[dict]:
    """Rank bookrunners by volume.

    Each issuance has 'lead_left_bookrunner' and 'issued_size_mm'.
    Returns ranked list: [{rank, bookrunner, deal_count, total_volume_mm, market_share_pct}].
    """
    if not issuances:
        return []

    totals: dict[str, dict] = {}
    grand_total = 0.0

    for iss in issuances:
        bookrunner = iss.get("lead_left_bookrunner")
        size = iss.get("issued_size_mm")
        if bookrunner is None or size is None:
            continue

        size = float(size)
        grand_total += size

        if bookrunner not in totals:
            totals[bookrunner] = {"deal_count": 0, "total_volume_mm": 0.0}
        totals[bookrunner]["deal_count"] += 1
        totals[bookrunner]["total_volume_mm"] += size

    if grand_total == 0:
        return []

    ranked = sorted(totals.items(), key=lambda x: x[1]["total_volume_mm"], reverse=True)

    result = []
    for rank, (bookrunner, stats) in enumerate(ranked, start=1):
        result.append({
            "rank": rank,
            "bookrunner": bookrunner,
            "deal_count": stats["deal_count"],
            "total_volume_mm": round(stats["total_volume_mm"], 2),
            "market_share_pct": round(stats["total_volume_mm"] / grand_total * 100, 2),
        })

    return result


def compute_tightening_stats(issuances: list[dict]) -> dict:
    """Compute average tightening from initial talk to final spread.

    Each issuance has 'initial_talk_low_bps', 'initial_talk_high_bps', 'final_spread_bps'.
    Returns {avg_tightening_bps, median_tightening_bps, count}.
    """
    tightenings: list[float] = []

    for iss in issuances:
        low = iss.get("initial_talk_low_bps")
        high = iss.get("initial_talk_high_bps")
        final = iss.get("final_spread_bps")
        if low is None or high is None or final is None:
            continue

        midpoint = (low + high) / 2.0
        tightening = midpoint - final
        tightenings.append(tightening)

    if not tightenings:
        return {"avg_tightening_bps": 0.0, "median_tightening_bps": 0.0, "count": 0}

    return {
        "avg_tightening_bps": round(sum(tightenings) / len(tightenings), 2),
        "median_tightening_bps": round(median(tightenings), 2),
        "count": len(tightenings),
    }
