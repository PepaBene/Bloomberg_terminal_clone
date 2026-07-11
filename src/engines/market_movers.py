"""Market Movers Engine.

Computes daily gainers/losers/most active from price data.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)

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


class MostActiveStatus(StrEnum):
    """Distinguishes *why* MOST_ACTIVE may be empty (P1-E-019).

    - ``OK``: at least one security had a reported volume.
    - ``QUIET_DAY``: valid price data existed for the session, but none of
      the securities had a reported volume — a data-quality/feed-coverage
      signal, not necessarily "the market was closed".
    - ``NO_DATA``: no securities passed the basic validity filters at all
      (e.g. no price data for the date), so there is nothing to rank.
    """

    OK = "OK"
    QUIET_DAY = "QUIET_DAY"
    NO_DATA = "NO_DATA"


@dataclass
class MoversComputationMeta:
    """Diagnostic metadata about ``compute_daily_movers`` (P1-E-018 / P1-E-019).

    Exposed as an extra ``"meta"`` key alongside ``TOP_GAINERS``/
    ``TOP_LOSERS``/``MOST_ACTIVE`` in the dict returned by
    ``compute_daily_movers`` — existing callers that do
    ``computed.get(category, [])`` for those three category keys are
    unaffected by this addition.
    """

    total_input: int = 0
    valid_count: int = 0
    excluded_missing_price_or_prior: int = 0
    excluded_low_prior_price: int = 0
    excluded_low_volume: int = 0
    excluded_extreme_change: int = 0
    most_active_status: MostActiveStatus = MostActiveStatus.NO_DATA


def compute_daily_movers(
    securities: list[dict],
    top_n: int = 10,
    max_change_pct: float = MAX_DAILY_CHANGE_PCT,
    min_prior_price: float = MIN_PRIOR_PRICE,
    min_volume: float = MIN_VOLUME,
) -> dict[str, list[MoverEntry] | MoversComputationMeta]:
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
    dict with keys: TOP_GAINERS, TOP_LOSERS, MOST_ACTIVE (lists of
    ``MoverEntry``), plus a ``"meta"`` key (``MoversComputationMeta``) with
    exclusion counts and a ``most_active_status`` flag (P1-E-018 / P1-E-019).
    The three category keys keep their original list-of-``MoverEntry``
    shape so existing ``computed.get(category, [])`` callers are unaffected.
    """
    entries = []
    excluded_missing_price_or_prior = 0
    excluded_low_prior_price = 0
    excluded_low_volume = 0
    excluded_extreme_change = 0

    for sec in securities:
        price = sec.get("price")
        prior = sec.get("prior_price")
        volume = sec.get("volume")
        # Guard against missing / non-positive / near-zero prior prices that
        # make the percentage explode or be undefined.
        if price is None or prior is None or prior <= 0:
            excluded_missing_price_or_prior += 1
            continue
        if prior < min_prior_price:
            excluded_low_prior_price += 1
            continue
        # Drop illiquid securities only when volume is actually reported.
        if volume is not None and volume < min_volume:
            excluded_low_volume += 1
            continue

        pct_change = (price - prior) / prior * 100

        # Sanity bound: reject absurd single-day moves that indicate bad data.
        if abs(pct_change) > max_change_pct:
            excluded_extreme_change += 1
            continue

        entries.append({
            "security_id": str(sec.get("security_id", "")),
            "name": sec.get("name"),
            "ticker": sec.get("ticker"),
            "price": price,
            "change_pct": round(pct_change, 4),
            "volume": sec.get("volume"),
        })

    total_excluded = (
        excluded_missing_price_or_prior
        + excluded_low_prior_price
        + excluded_low_volume
        + excluded_extreme_change
    )
    if total_excluded:
        # P1-E-018: previously these rows were dropped with zero logging,
        # making a real data-quality regression (e.g. a feed suddenly
        # omitting prior_price for most securities) silently invisible.
        logger.warning(
            "compute_daily_movers excluded %d/%d securities "
            "(missing_price_or_prior=%d, low_prior_price=%d, low_volume=%d, "
            "extreme_change=%d)",
            total_excluded,
            len(securities),
            excluded_missing_price_or_prior,
            excluded_low_prior_price,
            excluded_low_volume,
            excluded_extreme_change,
        )

    # Top gainers (highest pct change)
    gainers = sorted(entries, key=lambda x: x["change_pct"], reverse=True)[:top_n]
    # Top losers (lowest pct change)
    losers = sorted(entries, key=lambda x: x["change_pct"])[:top_n]
    # Most active (highest volume)
    active_all = [e for e in entries if e["volume"] is not None]
    active = sorted(active_all, key=lambda x: x["volume"], reverse=True)[:top_n]

    # P1-E-019: distinguish "no usable data at all" from "data present but
    # nobody reported volume" instead of both silently producing [].
    if not entries:
        most_active_status = MostActiveStatus.NO_DATA
        logger.info(
            "compute_daily_movers: MOST_ACTIVE has no data — no securities "
            "passed validity filters (0 of %d input rows usable)",
            len(securities),
        )
    elif not active_all:
        most_active_status = MostActiveStatus.QUIET_DAY
        logger.info(
            "compute_daily_movers: MOST_ACTIVE is empty — %d securities had "
            "valid price data but none reported volume (quiet day / "
            "feed gap, not a genuine no-data condition)",
            len(entries),
        )
    else:
        most_active_status = MostActiveStatus.OK

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

    meta = MoversComputationMeta(
        total_input=len(securities),
        valid_count=len(entries),
        excluded_missing_price_or_prior=excluded_missing_price_or_prior,
        excluded_low_prior_price=excluded_low_prior_price,
        excluded_low_volume=excluded_low_volume,
        excluded_extreme_change=excluded_extreme_change,
        most_active_status=most_active_status,
    )

    return {
        "TOP_GAINERS": _to_movers(gainers),
        "TOP_LOSERS": _to_movers(losers),
        "MOST_ACTIVE": _to_movers(active),
        "meta": meta,
    }
