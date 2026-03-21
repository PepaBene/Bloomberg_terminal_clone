"""Custom Index Engine.

Provides index weight computation, performance calculation, and rebalancing.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import math


def compute_index_weights(
    security_ids: list[str],
    method: str = "EQUAL",
    market_caps: list[float] | None = None,
    scores: list[float] | None = None,
    max_constituents: int | None = None,
) -> dict[str, float]:
    """Compute index weights using the specified method.

    Parameters
    ----------
    security_ids : List of security identifiers.
    method : EQUAL, MARKET_CAP, or SCORE_BASED.
    market_caps : Market capitalizations (required for MARKET_CAP).
    scores : Scores for weighting (required for SCORE_BASED).
    max_constituents : Max number of constituents to include.

    Returns
    -------
    dict mapping security_id → weight (sums to ~1.0).
    """
    if not security_ids:
        return {}

    selected = security_ids[:max_constituents] if max_constituents else security_ids

    if method == "MARKET_CAP" and market_caps:
        pairs = sorted(
            zip(selected, market_caps[:len(selected)]),
            key=lambda x: x[1], reverse=True,
        )
        if max_constituents:
            pairs = pairs[:max_constituents]
        total = sum(mc for _, mc in pairs)
        if total <= 0:
            return _equal_weights(selected)
        return {sid: round(mc / total, 6) for sid, mc in pairs}

    if method == "SCORE_BASED" and scores:
        pairs = sorted(
            zip(selected, scores[:len(selected)]),
            key=lambda x: x[1], reverse=True,
        )
        if max_constituents:
            pairs = pairs[:max_constituents]
        total = sum(max(s, 0) for _, s in pairs)
        if total <= 0:
            return _equal_weights([sid for sid, _ in pairs])
        return {sid: round(max(s, 0) / total, 6) for sid, s in pairs}

    # Default: equal weight
    return _equal_weights(selected)


def _equal_weights(ids: list[str]) -> dict[str, float]:
    n = len(ids)
    if n == 0:
        return {}
    w = round(1.0 / n, 6)
    return {sid: w for sid in ids}


def compute_index_performance(
    daily_returns: list[float],
    base_level: float = 1000.0,
) -> list[dict]:
    """Compute index levels and cumulative returns from daily returns.

    Returns list of {index_level, daily_return, cumulative_return}.
    """
    results = []
    level = base_level
    for r in daily_returns:
        level *= (1 + r)
        cum_return = (level / base_level) - 1
        results.append({
            "index_level": round(level, 4),
            "daily_return": round(r, 8),
            "cumulative_return": round(cum_return, 6),
        })
    return results


def rebalance_index(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    transaction_cost_bps: float = 10.0,
) -> dict:
    """Compute rebalance trades and costs.

    Returns {trades: [{security_id, old_weight, new_weight, trade_weight}], total_turnover, cost_bps}.
    """
    all_ids = set(current_weights.keys()) | set(target_weights.keys())
    trades = []
    total_turnover = 0.0

    for sid in sorted(all_ids):
        old_w = current_weights.get(sid, 0.0)
        new_w = target_weights.get(sid, 0.0)
        trade_w = new_w - old_w
        if abs(trade_w) > 1e-8:
            trades.append({
                "security_id": sid,
                "old_weight": round(old_w, 6),
                "new_weight": round(new_w, 6),
                "trade_weight": round(trade_w, 6),
            })
            total_turnover += abs(trade_w)

    cost = total_turnover * transaction_cost_bps / 10000

    return {
        "trades": trades,
        "total_turnover": round(total_turnover, 6),
        "cost_bps": round(cost * 10000, 2),
    }
