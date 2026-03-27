"""Pillar 3 Phase 3B — Global Intelligence: Commodity Intelligence Engine.

Pure computation engine for commodity market analysis.
Computes returns, percentiles, supply/demand balance, company exposure,
sensitivity scoring, correlation, scenario analysis, and anomaly detection.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev


# ── Constants ──────────────────────────────────────────────────────────

COMMODITY_CATEGORIES: dict[str, list[str]] = {
    "ENERGY": ["WTI", "BRENT", "HENRY_HUB", "LNG", "GASOLINE"],
    "PRECIOUS_METALS": ["GOLD", "SILVER", "PLATINUM"],
    "INDUSTRIAL_METALS": [
        "COPPER", "ALUMINUM", "ZINC", "NICKEL", "STEEL_HRC", "LITHIUM",
    ],
    "AGRICULTURE": [
        "CORN", "WHEAT", "SOYBEANS", "RICE", "COFFEE", "SUGAR", "COCOA",
        "COTTON",
    ],
    "LIVESTOCK": ["CATTLE", "HOGS"],
}

EXPOSURE_TYPES: dict[str, str] = {
    "PRODUCER": "Revenue directly tied to commodity price",
    "CONSUMER": "Commodity is a cost input",
    "INDIRECT": "Second-order exposure",
}

# Sectors that are producers of commodities
_PRODUCER_SECTORS = {"ENERGY", "OIL_GAS", "MINING", "METALS_MINING", "MATERIALS"}
# Sectors that consume commodities as cost inputs
_CONSUMER_SECTORS = {
    "AIRLINES", "INDUSTRIALS", "TRANSPORTATION", "MANUFACTURING",
    "CHEMICALS", "CONSUMER_STAPLES", "FOOD_BEVERAGE", "AUTOMOTIVE",
    "UTILITIES",
}

# Period definitions in calendar days
DEFAULT_PERIODS: dict[str, int] = {
    "1d": 1,
    "1w": 7,
    "1m": 30,
    "3m": 90,
    "1y": 365,
    "5y": 1825,
}


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class CommoditySnapshot:
    """Point-in-time snapshot of a commodity's price positioning."""
    commodity_code: str
    current_price: float
    price_change_1d_pct: float | None
    price_change_1w_pct: float | None
    price_change_1m_pct: float | None
    price_change_3m_pct: float | None
    price_change_1y_pct: float | None
    percentile_1y: float | None  # 0-100 where in 1Y range
    percentile_5y: float | None


@dataclass
class CommodityImpact:
    """Impact of a commodity price move on a single entity."""
    entity_id: str
    entity_name: str
    exposure_type: str  # PRODUCER / CONSUMER / INDIRECT
    sensitivity_score: float  # 0-100
    estimated_revenue_impact_pct: float | None
    direction: str  # POSITIVE / NEGATIVE (from price increase perspective)


@dataclass
class ScenarioResult:
    """Result of running a commodity price scenario."""
    commodity_code: str
    scenario_price: float
    price_change_pct: float
    affected_companies: list[CommodityImpact]
    total_affected: int
    most_impacted: list[str]  # top 5 entity names


# ── 1. Compute returns ────────────────────────────────────────────────

def compute_returns(
    prices: list[dict],
    periods: dict | None = None,
) -> dict:
    """Calculate percentage returns for standard time periods.

    Parameters
    ----------
    prices : list[dict]
        Each dict has ``date`` (str ISO) and ``close_price`` (float).
        Must be sorted chronologically (oldest first).
    periods : dict | None
        Override period definitions {name: days}.  Defaults to
        1d, 1w, 1m, 3m, 1y, 5y.

    Returns
    -------
    dict  {period_name: pct_change} — missing periods are omitted.
    """
    if len(prices) < 2:
        return {}

    periods = periods or DEFAULT_PERIODS
    latest = prices[-1]
    latest_price = latest["close_price"]

    results: dict[str, float] = {}
    for period_name, days in periods.items():
        if days >= len(prices):
            continue
        ref_idx = len(prices) - 1 - days
        if ref_idx < 0:
            continue
        ref_price = prices[ref_idx]["close_price"]
        if ref_price == 0:
            continue
        pct = ((latest_price - ref_price) / ref_price) * 100.0
        results[period_name] = round(pct, 4)

    return results


# ── 2. Compute price percentile ──────────────────────────────────────

def compute_price_percentile(
    current_price: float,
    history: list[float],
) -> float:
    """Percentage of historical prices that are below the current price.

    Returns a value in [0, 100].
    """
    if not history:
        return 50.0

    below = sum(1 for p in history if p < current_price)
    return round((below / len(history)) * 100.0, 2)


# ── 3. Build commodity snapshot ──────────────────────────────────────

def build_commodity_snapshot(
    commodity_code: str,
    prices: list[dict],
) -> CommoditySnapshot:
    """Assemble a ``CommoditySnapshot`` from raw price history.

    Parameters
    ----------
    commodity_code : str
    prices : list[dict]
        Sorted oldest-first.  Each: {date, close_price}.
    """
    if not prices:
        return CommoditySnapshot(
            commodity_code=commodity_code,
            current_price=0.0,
            price_change_1d_pct=None,
            price_change_1w_pct=None,
            price_change_1m_pct=None,
            price_change_3m_pct=None,
            price_change_1y_pct=None,
            percentile_1y=None,
            percentile_5y=None,
        )

    returns = compute_returns(prices)
    current_price = prices[-1]["close_price"]

    all_close = [p["close_price"] for p in prices]
    # 1Y percentile — last 365 prices
    history_1y = all_close[-365:] if len(all_close) >= 365 else all_close
    percentile_1y = compute_price_percentile(current_price, history_1y)

    # 5Y percentile — last 1825 prices
    history_5y = all_close[-1825:] if len(all_close) >= 1825 else all_close
    percentile_5y = compute_price_percentile(current_price, history_5y)

    return CommoditySnapshot(
        commodity_code=commodity_code,
        current_price=current_price,
        price_change_1d_pct=returns.get("1d"),
        price_change_1w_pct=returns.get("1w"),
        price_change_1m_pct=returns.get("1m"),
        price_change_3m_pct=returns.get("3m"),
        price_change_1y_pct=returns.get("1y"),
        percentile_1y=percentile_1y,
        percentile_5y=percentile_5y,
    )


# ── 4. Supply / demand balance ───────────────────────────────────────

def compute_supply_demand_balance(
    supply_data: dict,
    demand_data: dict,
) -> str:
    """Classify the supply/demand balance.

    Parameters
    ----------
    supply_data : dict  with ``total`` (float) key.
    demand_data : dict  with ``total`` (float) key.

    Returns
    -------
    str  — ``SURPLUS``, ``DEFICIT``, or ``BALANCED``.
    """
    supply = supply_data.get("total", 0.0)
    demand = demand_data.get("total", 0.0)

    if demand == 0:
        return "SURPLUS" if supply > 0 else "BALANCED"

    ratio = supply / demand
    if ratio > 1.05:
        return "SURPLUS"
    if ratio < 0.95:
        return "DEFICIT"
    return "BALANCED"


# ── 5. Classify company exposure ─────────────────────────────────────

def classify_company_exposure(
    entity_sector: str,
    entity_segments: dict | None,
    commodity_code: str,
) -> str:
    """Determine whether a company is PRODUCER, CONSUMER, or INDIRECT.

    Parameters
    ----------
    entity_sector : str
        GICS sector or sub-industry of the entity (upper-cased internally).
    entity_segments : dict | None
        Optional segment breakdown: {segment_name: revenue_pct}.
    commodity_code : str
        Commodity identifier (e.g. ``WTI``, ``COPPER``).
    """
    sector_upper = entity_sector.upper().replace(" ", "_")

    # Check segments for direct commodity mentions
    if entity_segments:
        for seg_name in entity_segments:
            if commodity_code.upper() in seg_name.upper():
                return "PRODUCER"

    if sector_upper in _PRODUCER_SECTORS:
        return "PRODUCER"
    if sector_upper in _CONSUMER_SECTORS:
        return "CONSUMER"
    return "INDIRECT"


# ── 6. Compute sensitivity score ─────────────────────────────────────

def compute_sensitivity_score(
    exposure_type: str,
    revenue_exposure_pct: float | None,
    historical_correlation: float | None,
) -> float:
    """Compute a 0-100 sensitivity score for an entity's commodity exposure.

    Scoring
    -------
    - Base score from exposure type: PRODUCER 60, CONSUMER 40, INDIRECT 15.
    - Revenue exposure adds up to +25 (scaled linearly from 0-100).
    - Historical correlation adds up to +15 (abs value * 15).
    """
    base_scores = {"PRODUCER": 60, "CONSUMER": 40, "INDIRECT": 15}
    score = base_scores.get(exposure_type, 15)

    if revenue_exposure_pct is not None:
        score += min(25.0, (revenue_exposure_pct / 100.0) * 25.0)

    if historical_correlation is not None:
        score += min(15.0, abs(historical_correlation) * 15.0)

    return round(min(100.0, max(0.0, score)), 2)


# ── 7. Compute historical correlation ────────────────────────────────

def compute_historical_correlation(
    equity_returns: list[float],
    commodity_returns: list[float],
) -> float:
    """Pearson correlation between equity and commodity return series.

    Truncates the longer series to match the shorter one.
    Returns 0.0 if either series has fewer than 3 data points or zero variance.
    """
    min_len = min(len(equity_returns), len(commodity_returns))
    if min_len < 3:
        return 0.0

    eq = equity_returns[:min_len]
    co = commodity_returns[:min_len]

    eq_mean = mean(eq)
    co_mean = mean(co)

    numerator = sum((e - eq_mean) * (c - co_mean) for e, c in zip(eq, co))
    eq_var = sum((e - eq_mean) ** 2 for e in eq)
    co_var = sum((c - co_mean) ** 2 for c in co)

    denom = (eq_var * co_var) ** 0.5
    if denom == 0:
        return 0.0

    return round(numerator / denom, 4)


# ── 8. Run commodity scenario ─────────────────────────────────────────

def run_commodity_scenario(
    current_price: float,
    scenario_price: float,
    exposed_companies: list[dict],
) -> ScenarioResult:
    """What happens to companies if a commodity moves to *scenario_price*.

    Parameters
    ----------
    current_price : float
    scenario_price : float
    exposed_companies : list[dict]
        Each company dict must contain:
        - entity_id, entity_name, exposure_type, sensitivity_score
        - revenue_exposure_pct (optional)
        - commodity_code (optional)

    Returns
    -------
    ScenarioResult
    """
    if current_price == 0:
        price_change_pct = 0.0
    else:
        price_change_pct = ((scenario_price - current_price) / current_price) * 100.0

    impacts: list[CommodityImpact] = []
    for co in exposed_companies:
        exposure = co.get("exposure_type", "INDIRECT")
        sensitivity = co.get("sensitivity_score", 0.0)
        rev_pct = co.get("revenue_exposure_pct")

        # Determine direction from a price-increase perspective
        price_up = price_change_pct >= 0
        if exposure == "PRODUCER":
            direction = "POSITIVE" if price_up else "NEGATIVE"
        elif exposure == "CONSUMER":
            direction = "NEGATIVE" if price_up else "POSITIVE"
        else:
            direction = "NEGATIVE" if price_up else "POSITIVE"

        # Estimate revenue impact
        estimated_rev_impact = None
        if rev_pct is not None:
            estimated_rev_impact = round(
                (price_change_pct / 100.0) * rev_pct * (sensitivity / 100.0), 4,
            )
            if exposure in ("CONSUMER", "INDIRECT"):
                estimated_rev_impact = -estimated_rev_impact

        impacts.append(CommodityImpact(
            entity_id=co["entity_id"],
            entity_name=co["entity_name"],
            exposure_type=exposure,
            sensitivity_score=sensitivity,
            estimated_revenue_impact_pct=estimated_rev_impact,
            direction=direction,
        ))

    # Sort by sensitivity descending for most-impacted
    impacts.sort(key=lambda x: -x.sensitivity_score)
    most_impacted = [imp.entity_name for imp in impacts[:5]]

    commodity_code = ""
    if exposed_companies:
        commodity_code = exposed_companies[0].get("commodity_code", "")

    return ScenarioResult(
        commodity_code=commodity_code,
        scenario_price=scenario_price,
        price_change_pct=round(price_change_pct, 4),
        affected_companies=impacts,
        total_affected=len(impacts),
        most_impacted=most_impacted,
    )


# ── 9. Detect price anomaly ──────────────────────────────────────────

def detect_price_anomaly(
    prices: list[float],
    threshold_sigma: float = 2.0,
) -> tuple[bool, float | None]:
    """Check if the latest price is an anomaly (> threshold sigma from mean).

    Returns
    -------
    (is_anomaly, z_score | None)
    """
    if len(prices) < 3:
        return (False, None)

    mu = mean(prices)
    sd = stdev(prices)
    if sd == 0:
        return (False, 0.0)

    latest = prices[-1]
    z = (latest - mu) / sd

    return (abs(z) > threshold_sigma, round(z, 4))


# ── 10. Get commodity category ───────────────────────────────────────

def get_commodity_category(commodity_code: str) -> str | None:
    """Look up the category for a commodity code from COMMODITY_CATEGORIES."""
    code = commodity_code.upper()
    for category, codes in COMMODITY_CATEGORIES.items():
        if code in codes:
            return category
    return None
