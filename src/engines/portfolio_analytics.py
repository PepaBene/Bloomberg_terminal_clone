"""Pillar 4 Phase 1 — Portfolio-Level Analytics Engine.

Pure computation engine for portfolio summaries, sector allocation,
concentration metrics, PnL analysis, and cash utilization.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from datetime import datetime


# ── Portfolio Summary ──────────────────────────────────────────────────


def compute_portfolio_summary(
    positions: list[dict],
    cash: float,
    nav: float,
) -> dict:
    """Compute portfolio-level summary statistics.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, market_value, weight, ...}.
    cash : float
        Cash balance.
    nav : float
        Total NAV (market_value + cash).

    Returns
    -------
    dict
        {total_positions, market_value, cash_pct, invested_pct, avg_position_size}
    """
    total_positions = len(positions)
    market_value = sum(p.get("market_value", 0.0) for p in positions)
    cash_pct = (cash / nav * 100.0) if nav > 0 else 0.0
    invested_pct = 100.0 - cash_pct if nav > 0 else 0.0
    avg_position_size = (
        market_value / total_positions if total_positions > 0 else 0.0
    )

    return {
        "total_positions": total_positions,
        "market_value": round(market_value, 2),
        "cash_pct": round(cash_pct, 2),
        "invested_pct": round(invested_pct, 2),
        "avg_position_size": round(avg_position_size, 2),
    }


# ── Sector Allocation ─────────────────────────────────────────────────


def compute_sector_allocation(positions: list[dict]) -> list[dict]:
    """Compute allocation by sector.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, sector, market_value, weight, ...}.

    Returns
    -------
    list[dict]
        [{sector, weight, count, market_value}] sorted by weight desc.
    """
    sector_map: dict[str, dict] = {}
    total_mv = sum(p.get("market_value", 0.0) for p in positions)

    for p in positions:
        sector = p.get("sector", "Unknown")
        if sector not in sector_map:
            sector_map[sector] = {"market_value": 0.0, "count": 0}
        sector_map[sector]["market_value"] += p.get("market_value", 0.0)
        sector_map[sector]["count"] += 1

    result: list[dict] = []
    for sector, data in sector_map.items():
        weight = (
            (data["market_value"] / total_mv * 100.0) if total_mv > 0 else 0.0
        )
        result.append({
            "sector": sector,
            "weight": round(weight, 2),
            "count": data["count"],
            "market_value": round(data["market_value"], 2),
        })

    result.sort(key=lambda x: -x["weight"])
    return result


# ── Top Holdings ───────────────────────────────────────────────────────


def compute_top_holdings(
    positions: list[dict],
    n: int = 5,
) -> list[dict]:
    """Return top N holdings by weight.

    Parameters
    ----------
    positions : list[dict]
        Each must have 'weight' field.
    n : int
        Number of top holdings to return.

    Returns
    -------
    list[dict]
        Top N positions sorted by weight descending.
    """
    sorted_positions = sorted(
        positions, key=lambda p: p.get("weight", 0.0), reverse=True,
    )
    return sorted_positions[:n]


# ── Concentration (HHI) ───────────────────────────────────────────────


def compute_concentration_hhi(weights: list[float]) -> float:
    """Compute Herfindahl-Hirschman Index.

    HHI = sum of squared weights * 10000.
    Weights should be in decimal form (e.g. 0.10 for 10%).
    """
    return sum(w * w for w in weights) * 10000.0


def classify_concentration(hhi: float) -> str:
    """Classify portfolio concentration based on HHI.

    <500  → DIVERSIFIED
    500-1500 → MODERATE
    >1500 → CONCENTRATED
    """
    if hhi < 500:
        return "DIVERSIFIED"
    elif hhi <= 1500:
        return "MODERATE"
    else:
        return "CONCENTRATED"


def compute_effective_positions(hhi: float) -> float:
    """Compute effective number of positions: 10000 / HHI.

    Returns 0.0 if HHI is zero.
    """
    if hhi == 0.0:
        return 0.0
    return 10000.0 / hhi


# ── Unrealized PnL Summary ────────────────────────────────────────────


def compute_unrealized_pnl_summary(positions: list[dict]) -> dict:
    """Compute summary of unrealized gains and losses.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, unrealized_pnl, ...}.

    Returns
    -------
    dict
        {winners_count, losers_count, total_gain, total_loss, net_pnl, win_rate}
    """
    winners_count = 0
    losers_count = 0
    total_gain = 0.0
    total_loss = 0.0

    for p in positions:
        pnl = p.get("unrealized_pnl", 0.0)
        if pnl > 0:
            winners_count += 1
            total_gain += pnl
        elif pnl < 0:
            losers_count += 1
            total_loss += pnl

    total_positions = winners_count + losers_count
    win_rate = (
        (winners_count / total_positions * 100.0)
        if total_positions > 0
        else 0.0
    )

    return {
        "winners_count": winners_count,
        "losers_count": losers_count,
        "total_gain": round(total_gain, 2),
        "total_loss": round(total_loss, 2),
        "net_pnl": round(total_gain + total_loss, 2),
        "win_rate": round(win_rate, 2),
    }


# ── Cash Utilization ──────────────────────────────────────────────────


def compute_cash_utilization(
    cash: float,
    nav: float,
    min_cash_pct: float = 2.0,
    max_cash_pct: float = 15.0,
) -> dict:
    """Assess cash utilization relative to thresholds.

    Parameters
    ----------
    cash : float
        Cash balance.
    nav : float
        Total NAV.
    min_cash_pct : float
        Minimum acceptable cash percentage.
    max_cash_pct : float
        Maximum acceptable cash percentage.

    Returns
    -------
    dict
        {cash_pct, status, message}
    """
    cash_pct = (cash / nav * 100.0) if nav > 0 else 0.0

    if cash_pct < min_cash_pct:
        status = "UNDER_INVESTED"
        message = (
            f"Cash at {cash_pct:.1f}% is below minimum {min_cash_pct:.1f}%. "
            f"Consider raising cash for liquidity."
        )
    elif cash_pct > max_cash_pct:
        status = "OVER_CASH"
        message = (
            f"Cash at {cash_pct:.1f}% exceeds maximum {max_cash_pct:.1f}%. "
            f"Consider deploying capital."
        )
    else:
        status = "OPTIMAL"
        message = (
            f"Cash at {cash_pct:.1f}% is within optimal range "
            f"({min_cash_pct:.1f}%-{max_cash_pct:.1f}%)."
        )

    return {
        "cash_pct": round(cash_pct, 2),
        "status": status,
        "message": message,
    }


# ── Position Enrichment ───────────────────────────────────────────────


def enrich_position_with_p2(
    position: dict,
    ratios: dict | None,
) -> dict:
    """Enrich a position with Pillar 2 fundamental ratios.

    Parameters
    ----------
    position : dict
        Position data (ticker, market_value, etc.).
    ratios : dict | None
        Optional fundamental ratios (pe_ratio, roe, piotroski_score, etc.).

    Returns
    -------
    dict
        Position dict merged with available ratios.
    """
    enriched = dict(position)
    if ratios is not None:
        enriched["pe_ratio"] = ratios.get("pe_ratio")
        enriched["roe"] = ratios.get("roe")
        enriched["piotroski_score"] = ratios.get("piotroski_score")
        enriched["debt_to_equity"] = ratios.get("debt_to_equity")
        enriched["dividend_yield"] = ratios.get("dividend_yield")
    return enriched


# ── Portfolio Age ─────────────────────────────────────────────────────


def compute_portfolio_age(
    inception_date: str,
    as_of_date: str,
) -> dict:
    """Compute portfolio age from inception.

    Parameters
    ----------
    inception_date : str
        Portfolio inception date (YYYY-MM-DD).
    as_of_date : str
        Current date (YYYY-MM-DD).

    Returns
    -------
    dict
        {days, months, years}
    """
    inception = datetime.strptime(inception_date, "%Y-%m-%d")
    as_of = datetime.strptime(as_of_date, "%Y-%m-%d")
    delta = as_of - inception
    days = delta.days
    months = days / 30.44  # average days per month
    years = days / 365.25

    return {
        "days": days,
        "months": round(months, 1),
        "years": round(years, 2),
    }
