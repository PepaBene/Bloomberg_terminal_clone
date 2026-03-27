"""D11 FI Supplement P6: Credit Spread Analytics Engine.

Pure computation functions (no DB access) for credit spread analysis.
"""

from __future__ import annotations

import statistics

BAML_SERIES: dict[str, dict[str, str]] = {
    "BAMLC0A0CM": {"name": "US Corporate Master OAS", "category": "IG"},
    "BAMLC0A1CAAA": {"name": "US Corporate AAA OAS", "category": "AAA"},
    "BAMLC0A2CAA": {"name": "US Corporate AA OAS", "category": "AA"},
    "BAMLC0A3CA": {"name": "US Corporate A OAS", "category": "A"},
    "BAMLC0A4CBBB": {"name": "US Corporate BBB OAS", "category": "BBB"},
    "BAMLH0A0HYM2": {"name": "US High Yield Master OAS", "category": "HY"},
    "BAMLH0A1HYBB": {"name": "US High Yield BB OAS", "category": "BB"},
    "BAMLH0A2HYB": {"name": "US High Yield B OAS", "category": "B"},
    "BAMLH0A3HYC": {"name": "US High Yield CCC OAS", "category": "CCC"},
    "BAMLC0A0CMEY": {"name": "US Corporate Effective Yield", "category": "IG_YIELD"},
    "BAMLH0A0HYM2EY": {"name": "US High Yield Effective Yield", "category": "HY_YIELD"},
}


def compute_spread_percentile(values: list[float], current: float) -> dict:
    """Compute percentile rank, z-score, min, max, mean, std_dev for current value vs historical.

    Parameters
    ----------
    values : list[float]
        Historical spread values.
    current : float
        The current spread value to rank.

    Returns
    -------
    dict
        Keys: percentile, z_score, min_val, max_val, mean_val, std_dev.
    """
    if not values:
        return {
            "percentile": 0.0,
            "z_score": 0.0,
            "min_val": 0.0,
            "max_val": 0.0,
            "mean_val": 0.0,
            "std_dev": 0.0,
        }

    min_val = min(values)
    max_val = max(values)
    mean_val = statistics.mean(values)
    std_dev = statistics.pstdev(values) if len(values) > 1 else 0.0

    # Percentile rank: % of historical values that are <= current
    count_le = sum(1 for v in values if v <= current)
    percentile = (count_le / len(values)) * 100.0

    # Z-score
    z_score = (current - mean_val) / std_dev if std_dev > 0 else 0.0

    return {
        "percentile": round(percentile, 2),
        "z_score": round(z_score, 4),
        "min_val": round(min_val, 4),
        "max_val": round(max_val, 4),
        "mean_val": round(mean_val, 4),
        "std_dev": round(std_dev, 4),
    }


def detect_spread_regime(percentile: float) -> str:
    """Classify the current spread regime based on percentile rank.

    Returns
    -------
    str
        One of: TIGHT (<25th), NORMAL (25-75th), WIDE (75-90th), CRISIS (>90th).
    """
    if percentile < 25:
        return "TIGHT"
    elif percentile <= 75:
        return "NORMAL"
    elif percentile <= 90:
        return "WIDE"
    else:
        return "CRISIS"


def compute_ig_hy_differential(ig_oas: float, hy_oas: float) -> dict:
    """Compute ratio and spread between IG and HY OAS.

    Parameters
    ----------
    ig_oas : float
        Investment grade OAS (bps).
    hy_oas : float
        High yield OAS (bps).

    Returns
    -------
    dict
        Keys: ratio, spread.
    """
    ratio = hy_oas / ig_oas if ig_oas != 0 else 0.0
    spread = hy_oas - ig_oas

    return {
        "ratio": round(ratio, 4),
        "spread": round(spread, 4),
    }
