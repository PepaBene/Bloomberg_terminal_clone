"""Default Risk Scoring Engine.

Provides:
- Merton Distance-to-Default (iterative solver, pure Python, no scipy)
- Composite credit risk score combining Altman Z-Score + Merton DD
- Score-to-rating mapping
- Trend detection

All functions are pure computation — no database access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Normal CDF approximation (Abramowitz & Stegun, max error ~1.5e-7)
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    # Use math.erfc for better numerical stability
    return 0.5 * math.erfc(-x / math.sqrt(2))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


# ---------------------------------------------------------------------------
# Merton Distance-to-Default
# ---------------------------------------------------------------------------

@dataclass
class MertonResult:
    """Output of the Merton model."""
    distance_to_default: float
    probability_of_default: float
    asset_value: float
    asset_volatility: float


def merton_distance_to_default(
    equity_value: float,
    equity_volatility: float,
    total_debt: float,
    risk_free_rate: float,
    horizon: float = 1.0,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> MertonResult:
    """Compute Merton Distance-to-Default via iterative solver.

    Uses the KMV-Merton approach:
    - Equity = Call option on firm assets with strike = debt face value
    - Solve simultaneously for asset value (V) and asset volatility (σ_V)
    - DD = (ln(V/D) + (r - 0.5*σ_V²)*T) / (σ_V * √T)
    - PD = N(-DD)

    Parameters
    ----------
    equity_value : Market cap (e.g. share price × shares outstanding)
    equity_volatility : Annualized equity volatility (decimal, e.g. 0.30)
    total_debt : Total debt (short-term + 0.5 * long-term is common)
    risk_free_rate : Annualized risk-free rate (decimal, e.g. 0.045)
    horizon : Time horizon in years (default 1.0)
    max_iterations : Max iterations for convergence
    tolerance : Convergence tolerance

    Returns
    -------
    MertonResult
    """
    if equity_value <= 0 or total_debt <= 0 or equity_volatility <= 0:
        raise ValueError("equity_value, total_debt, and equity_volatility must be positive")
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    # Initial guesses
    V = equity_value + total_debt  # asset value
    sigma_V = equity_volatility * equity_value / V  # asset vol

    sqrt_T = math.sqrt(horizon)
    r = risk_free_rate

    for _ in range(max_iterations):
        # Black-Scholes d1, d2
        d1 = (math.log(V / total_debt) + (r + 0.5 * sigma_V**2) * horizon) / (sigma_V * sqrt_T)
        d2 = d1 - sigma_V * sqrt_T

        # Equity = V * N(d1) - D * exp(-r*T) * N(d2)
        V_new = (equity_value + total_debt * math.exp(-r * horizon) * _norm_cdf(d2)) / _norm_cdf(d1)

        # σ_E = σ_V * V * N'(d1) / E  →  σ_V = σ_E * E / (V * N(d1))
        sigma_V_new = equity_volatility * equity_value / (V_new * _norm_cdf(d1))

        # Check convergence
        if abs(V_new - V) < tolerance and abs(sigma_V_new - sigma_V) < tolerance:
            V = V_new
            sigma_V = sigma_V_new
            break

        V = V_new
        sigma_V = sigma_V_new

    # Compute DD and PD
    if sigma_V <= 0 or sqrt_T <= 0:
        dd = 0.0
    else:
        dd = (math.log(V / total_debt) + (r - 0.5 * sigma_V**2) * horizon) / (sigma_V * sqrt_T)

    pd = _norm_cdf(-dd)

    return MertonResult(
        distance_to_default=round(dd, 4),
        probability_of_default=round(pd, 8),
        asset_value=round(V, 2),
        asset_volatility=round(sigma_V, 6),
    )


# ---------------------------------------------------------------------------
# Composite Score
# ---------------------------------------------------------------------------

@dataclass
class CompositeResult:
    """Output of composite credit risk scoring."""
    score: float          # 1-100 (100 = safest)
    implied_rating: str
    credit_zone: str
    drivers: list[dict]   # [{driver, contribution, description}]


def compute_composite_score(
    altman_z: float | None = None,
    altman_zone: str | None = None,
    merton_dd: float | None = None,
    merton_pd: float | None = None,
    leverage_ratio: float | None = None,
    interest_coverage: float | None = None,
    cash_ratio: float | None = None,
) -> CompositeResult:
    """Compute a composite credit risk score from multiple inputs.

    The score is a weighted blend normalized to 1-100, where 100 = safest.

    Weights (when all inputs available):
    - Altman Z-Score:       25%
    - Merton DD:            25%
    - Leverage ratio:       20%
    - Interest coverage:    15%
    - Cash ratio:           15%

    Parameters
    ----------
    altman_z : Altman Z-Score (higher = safer)
    altman_zone : SAFE / GREY / DISTRESS
    merton_dd : Distance-to-default (higher = safer)
    merton_pd : Probability of default
    leverage_ratio : Total debt / total assets (lower = safer)
    interest_coverage : EBIT / interest expense (higher = safer)
    cash_ratio : Cash / current liabilities (higher = safer)

    Returns
    -------
    CompositeResult
    """
    components: list[tuple[str, float, float, str]] = []  # (name, sub_score, weight, desc)

    # --- Altman Z-Score sub-score (0-100) ---
    if altman_z is not None:
        if altman_z >= 3.0:
            sub = 100.0
        elif altman_z >= 2.7:
            sub = 80.0 + (altman_z - 2.7) / 0.3 * 20.0
        elif altman_z >= 1.8:
            sub = 40.0 + (altman_z - 1.8) / 0.9 * 40.0
        elif altman_z >= 1.1:
            sub = 15.0 + (altman_z - 1.1) / 0.7 * 25.0
        else:
            sub = max(0.0, altman_z / 1.1 * 15.0)
        components.append(("altman_z", sub, 0.25, f"Z={altman_z:.2f} zone={altman_zone or 'N/A'}"))

    # --- Merton DD sub-score (0-100) ---
    if merton_dd is not None:
        if merton_dd >= 4.0:
            sub = 100.0
        elif merton_dd >= 2.0:
            sub = 60.0 + (merton_dd - 2.0) / 2.0 * 40.0
        elif merton_dd >= 1.0:
            sub = 30.0 + (merton_dd - 1.0) / 1.0 * 30.0
        elif merton_dd >= 0.0:
            sub = merton_dd / 1.0 * 30.0
        else:
            sub = 0.0
        pd_str = f" PD={merton_pd:.4%}" if merton_pd is not None else ""
        components.append(("merton_dd", sub, 0.25, f"DD={merton_dd:.2f}{pd_str}"))

    # --- Leverage ratio sub-score (0-100, lower leverage = higher score) ---
    if leverage_ratio is not None:
        if leverage_ratio <= 0.2:
            sub = 100.0
        elif leverage_ratio <= 0.4:
            sub = 70.0 + (0.4 - leverage_ratio) / 0.2 * 30.0
        elif leverage_ratio <= 0.6:
            sub = 40.0 + (0.6 - leverage_ratio) / 0.2 * 30.0
        elif leverage_ratio <= 0.8:
            sub = 15.0 + (0.8 - leverage_ratio) / 0.2 * 25.0
        else:
            sub = max(0.0, 15.0 * (1.0 - leverage_ratio) / 0.2)
        components.append(("leverage", sub, 0.20, f"D/A={leverage_ratio:.2f}"))

    # --- Interest coverage sub-score (0-100) ---
    if interest_coverage is not None:
        if interest_coverage >= 10.0:
            sub = 100.0
        elif interest_coverage >= 5.0:
            sub = 70.0 + (interest_coverage - 5.0) / 5.0 * 30.0
        elif interest_coverage >= 2.0:
            sub = 30.0 + (interest_coverage - 2.0) / 3.0 * 40.0
        elif interest_coverage >= 1.0:
            sub = 10.0 + (interest_coverage - 1.0) / 1.0 * 20.0
        else:
            sub = max(0.0, interest_coverage / 1.0 * 10.0)
        components.append(("interest_coverage", sub, 0.15, f"ICR={interest_coverage:.2f}"))

    # --- Cash ratio sub-score (0-100) ---
    if cash_ratio is not None:
        if cash_ratio >= 1.0:
            sub = 100.0
        elif cash_ratio >= 0.5:
            sub = 60.0 + (cash_ratio - 0.5) / 0.5 * 40.0
        elif cash_ratio >= 0.2:
            sub = 25.0 + (cash_ratio - 0.2) / 0.3 * 35.0
        else:
            sub = max(0.0, cash_ratio / 0.2 * 25.0)
        components.append(("cash_ratio", sub, 0.15, f"Cash={cash_ratio:.2f}"))

    if not components:
        return CompositeResult(
            score=0.0, implied_rating="D", credit_zone="DISTRESSED",
            drivers=[{"driver": "no_data", "contribution": 0.0, "description": "No input data"}],
        )

    # Normalize weights to sum to 1.0
    total_weight = sum(w for _, _, w, _ in components)
    score = sum(s * w / total_weight for _, s, w, _ in components)
    score = round(min(100.0, max(1.0, score)), 1)

    # Build drivers sorted by contribution
    drivers = []
    for name, sub_score, weight, desc in components:
        contribution = round(sub_score * weight / total_weight, 1)
        drivers.append({"driver": name, "contribution": contribution, "description": desc})
    drivers.sort(key=lambda d: d["contribution"], reverse=True)

    rating = _map_score_to_rating(score)
    zone = _map_score_to_zone(score)

    return CompositeResult(score=score, implied_rating=rating, credit_zone=zone, drivers=drivers)


def _map_score_to_rating(score: float) -> str:
    """Map a 1-100 composite score to an implied credit rating."""
    thresholds = [
        (95, "AAA"), (90, "AA+"), (85, "AA"), (80, "AA-"),
        (75, "A+"), (70, "A"), (65, "A-"),
        (60, "BBB+"), (55, "BBB"), (50, "BBB-"),
        (45, "BB+"), (40, "BB"), (35, "BB-"),
        (30, "B+"), (25, "B"), (20, "B-"),
        (15, "CCC"), (10, "CC"), (5, "C"),
    ]
    for threshold, rating in thresholds:
        if score >= threshold:
            return rating
    return "D"


def _map_score_to_zone(score: float) -> str:
    """Map a 1-100 composite score to a credit zone."""
    if score >= 50:
        return "INVESTMENT_GRADE"
    elif score >= 35:
        return "CROSSOVER"
    elif score >= 20:
        return "HIGH_YIELD"
    else:
        return "DISTRESSED"


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

def detect_trend(
    current_score: float,
    prior_score: float | None,
) -> tuple[float | None, str]:
    """Detect score trend.

    Returns
    -------
    (score_change, trend)
        trend is IMPROVING / STABLE / DETERIORATING
    """
    if prior_score is None:
        return None, "STABLE"

    change = round(current_score - prior_score, 1)
    if change >= 5.0:
        trend = "IMPROVING"
    elif change <= -5.0:
        trend = "DETERIORATING"
    else:
        trend = "STABLE"
    return change, trend
