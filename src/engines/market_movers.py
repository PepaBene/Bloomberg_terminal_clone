"""Market Movers Engine.

Computes daily gainers/losers/most active from price data.
All functions are pure computation — no database access.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MoverEntry:
    """A single mover entry."""
    rank: int
    security_id: str
    name: str | None
    ticker: str | None
    price: float | None
    change_pct: float
    volume: float | None


def compute_daily_movers(
    securities: list[dict],
    top_n: int = 10,
) -> dict[str, list[MoverEntry]]:
    """Compute top gainers, losers, and most active from EOD data.

    Parameters
    ----------
    securities : list of dicts with keys:
        security_id, name, ticker, price, prior_price, volume
    top_n : Number of top entries per category.

    Returns
    -------
    dict with keys: TOP_GAINERS, TOP_LOSERS, MOST_ACTIVE
    """
    entries = []
    for sec in securities:
        price = sec.get("price")
        prior = sec.get("prior_price")
        if price is None or prior is None or prior <= 0:
            continue

        pct_change = (price - prior) / prior * 100

        entries.append({
            "security_id": str(sec.get("security_id", "")),
            "name": sec.get("name"),
            "ticker": sec.get("ticker"),
            "price": price,
            "change_pct": round(pct_change, 4),
            "volume": sec.get("volume"),
        })

    # Top gainers (highest pct change)
    gainers = sorted(entries, key=lambda x: x["change_pct"], reverse=True)[:top_n]
    # Top losers (lowest pct change)
    losers = sorted(entries, key=lambda x: x["change_pct"])[:top_n]
    # Most active (highest volume)
    active = sorted(
        [e for e in entries if e["volume"] is not None],
        key=lambda x: x["volume"], reverse=True,
    )[:top_n]

    def _to_movers(items: list[dict]) -> list[MoverEntry]:
        return [
            MoverEntry(
                rank=i + 1,
                security_id=item["security_id"],
                name=item["name"],
                ticker=item["ticker"],
                price=item["price"],
                change_pct=item["change_pct"],
                volume=item["volume"],
            )
            for i, item in enumerate(items)
        ]

    return {
        "TOP_GAINERS": _to_movers(gainers),
        "TOP_LOSERS": _to_movers(losers),
        "MOST_ACTIVE": _to_movers(active),
    }
