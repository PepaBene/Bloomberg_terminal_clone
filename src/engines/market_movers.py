"""Market Movers Engine.

Computes daily gainers/losers/most active from price data.
All functions are pure computation — no database access.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Data-quality sanity bounds ---------------------------------------------
# Daily EOD close-to-close moves are computed from consecutive trading days.
# Unadjusted split prices, feed glitches, and penny-stock ticks can produce
# absurd percentages (e.g. +593%). These bounds exclude such artifacts so the
# movers list reflects real market activity.
#
# MAX_DAILY_CHANGE_PCT: A single-session move of +/-50% comfortably captures
#   every legitimate large mover (limit-up/down halts, earnings gaps, biotech
#   binary events rarely exceed this on liquid names). Anything larger is far
#   more likely to be a stock split not yet adjusted or a bad price pair.
# MIN_PRIOR_PRICE: Sub-$1 prior prices are dominated by penny-stock tick noise
#   where a one-cent move is a huge percentage; requiring >= $1 filters this
#   out while keeping all normally-priced securities.
# MIN_VOLUME: A modest volume floor drops securities with no real liquidity
#   (stale/illiquid quotes). Kept conservative so genuine movers aren't lost;
#   None volume is tolerated (not all feeds populate it).
MAX_DAILY_CHANGE_PCT = 50.0
MIN_PRIOR_PRICE = 1.0
MIN_VOLUME = 1000.0


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
    max_change_pct: float = MAX_DAILY_CHANGE_PCT,
    min_prior_price: float = MIN_PRIOR_PRICE,
    min_volume: float = MIN_VOLUME,
) -> dict[str, list[MoverEntry]]:
    """Compute top gainers, losers, and most active from EOD data.

    Parameters
    ----------
    securities : list of dicts with keys:
        security_id, name, ticker, price, prior_price, volume
    top_n : Number of top entries per category.
    max_change_pct : Exclude any security whose |change_pct| exceeds this
        bound. Defaults to ``MAX_DAILY_CHANGE_PCT`` (50%) to drop data-quality
        artifacts (unadjusted splits, bad price pairs).
    min_prior_price : Minimum prior close required; drops penny-stock tick
        noise. Defaults to ``MIN_PRIOR_PRICE`` ($1).
    min_volume : Minimum volume required when volume is known; excludes
        illiquid noise. ``None`` volume is tolerated. Defaults to
        ``MIN_VOLUME``.

    Returns
    -------
    dict with keys: TOP_GAINERS, TOP_LOSERS, MOST_ACTIVE
    """
    entries = []
    for sec in securities:
        price = sec.get("price")
        prior = sec.get("prior_price")
        volume = sec.get("volume")
        # Guard against missing / non-positive / near-zero prior prices that
        # make the percentage explode or be undefined.
        if price is None or prior is None or prior <= 0:
            continue
        if prior < min_prior_price:
            continue
        # Drop illiquid securities only when volume is actually reported.
        if volume is not None and volume < min_volume:
            continue

        pct_change = (price - prior) / prior * 100

        # Sanity bound: reject absurd single-day moves that indicate bad data.
        if abs(pct_change) > max_change_pct:
            continue

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
