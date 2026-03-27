"""Pillar 4 Phase 3 — Drift Engine.

Pure computation engine for portfolio drift analysis, rebalance
suggestions, tracking error, and drift alerting.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────────

DRIFT_THRESHOLDS = {"MINIMAL": 2.0, "MODERATE": 5.0, "SIGNIFICANT": 10.0}
REBALANCE_THRESHOLD = 5.0


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class PositionDrift:
    """Drift for a single position."""

    ticker: str
    target_weight: float
    current_weight: float
    drift_pct: float  # current - target
    abs_drift: float
    action_needed: str  # BUY / SELL / HOLD


@dataclass
class SectorDrift:
    """Drift for a single sector."""

    sector: str
    target_weight: float
    current_weight: float
    drift_pct: float


@dataclass
class DriftResult:
    """Full drift analysis result."""

    total_drift_pct: float  # sum of absolute drifts / 2
    max_position_drift_pct: float
    max_sector_drift_pct: float
    classification: str  # MINIMAL / MODERATE / SIGNIFICANT / CRITICAL
    rebalance_needed: bool
    position_drifts: list[PositionDrift]
    sector_drifts: list[SectorDrift]
    rebalance_trades: list[dict]  # suggested trades to get back to target


@dataclass
class DriftAlert:
    """A single drift alert."""

    alert_type: str
    severity: str
    message: str
    drift_details: dict


# ── Position Drift ───────────────────────────────────────────────────────


def compute_position_drift(
    current_weights: dict,
    target_weights: dict,
) -> list[PositionDrift]:
    """Compute per-position drift between current and target weights.

    Parameters
    ----------
    current_weights : dict
        Mapping ticker -> current weight (percentage).
    target_weights : dict
        Mapping ticker -> target weight (percentage).

    Returns
    -------
    list[PositionDrift]
        Sorted by absolute drift descending.
    """
    all_tickers = set(current_weights.keys()) | set(target_weights.keys())
    drifts: list[PositionDrift] = []

    for ticker in all_tickers:
        current = current_weights.get(ticker, 0.0)
        target = target_weights.get(ticker, 0.0)
        drift = current - target
        abs_drift = abs(drift)

        if drift > 0.01:
            action = "SELL"
        elif drift < -0.01:
            action = "BUY"
        else:
            action = "HOLD"

        drifts.append(PositionDrift(
            ticker=ticker,
            target_weight=target,
            current_weight=current,
            drift_pct=round(drift, 4),
            abs_drift=round(abs_drift, 4),
            action_needed=action,
        ))

    drifts.sort(key=lambda d: -d.abs_drift)
    return drifts


# ── Sector Drift ─────────────────────────────────────────────────────────


def compute_sector_drift(
    positions: list[dict],
    target_sector_weights: dict,
) -> list[SectorDrift]:
    """Compute per-sector drift.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, sector, weight, ...}. Weight in percentage.
    target_sector_weights : dict
        Mapping sector -> target weight (percentage).

    Returns
    -------
    list[SectorDrift]
        Sorted by absolute drift descending.
    """
    current_sector_weights: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        current_sector_weights[sector] = (
            current_sector_weights.get(sector, 0.0) + p.get("weight", 0.0)
        )

    all_sectors = set(current_sector_weights.keys()) | set(target_sector_weights.keys())
    drifts: list[SectorDrift] = []

    for sector in all_sectors:
        current = current_sector_weights.get(sector, 0.0)
        target = target_sector_weights.get(sector, 0.0)
        drift = current - target

        drifts.append(SectorDrift(
            sector=sector,
            target_weight=round(target, 4),
            current_weight=round(current, 4),
            drift_pct=round(drift, 4),
        ))

    drifts.sort(key=lambda d: -abs(d.drift_pct))
    return drifts


# ── Total Drift ──────────────────────────────────────────────────────────


def compute_total_drift(position_drifts: list[PositionDrift]) -> float:
    """Compute total portfolio drift: sum of absolute drifts / 2.

    This measures the minimum percentage of the portfolio that would
    need to be traded to return to target weights.

    Parameters
    ----------
    position_drifts : list[PositionDrift]

    Returns
    -------
    float
        Total drift percentage.
    """
    return round(sum(d.abs_drift for d in position_drifts) / 2.0, 4)


# ── Classification ───────────────────────────────────────────────────────


def classify_drift(total_drift: float) -> str:
    """Classify drift severity.

    Parameters
    ----------
    total_drift : float
        Total drift percentage.

    Returns
    -------
    str
        MINIMAL / MODERATE / SIGNIFICANT / CRITICAL
    """
    if total_drift <= DRIFT_THRESHOLDS["MINIMAL"]:
        return "MINIMAL"
    elif total_drift <= DRIFT_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    elif total_drift <= DRIFT_THRESHOLDS["SIGNIFICANT"]:
        return "SIGNIFICANT"
    else:
        return "CRITICAL"


# ── Rebalance Suggestions ───────────────────────────────────────────────


def suggest_rebalance_trades(
    position_drifts: list[PositionDrift],
    portfolio_nav: float,
) -> list[dict]:
    """Suggest trades to reduce drift back to target weights.

    Parameters
    ----------
    position_drifts : list[PositionDrift]
    portfolio_nav : float
        Total portfolio net asset value.

    Returns
    -------
    list[dict]
        [{ticker, action, weight_delta, notional_amount}] sorted by
        notional amount descending.
    """
    if portfolio_nav <= 0:
        return []

    trades: list[dict] = []

    for d in position_drifts:
        if d.action_needed == "HOLD":
            continue

        weight_delta = d.abs_drift
        notional = round(weight_delta / 100.0 * portfolio_nav, 2)

        trades.append({
            "ticker": d.ticker,
            "action": d.action_needed,
            "weight_delta": round(weight_delta, 4),
            "notional_amount": notional,
        })

    trades.sort(key=lambda t: -t["notional_amount"])
    return trades


# ── Drift Alerts ─────────────────────────────────────────────────────────


def generate_drift_alerts(
    drift_result: DriftResult,
    prior_drift: DriftResult | None = None,
) -> list[DriftAlert]:
    """Generate alerts based on drift analysis.

    Parameters
    ----------
    drift_result : DriftResult
        Current drift analysis.
    prior_drift : DriftResult | None
        Previous drift result for comparison (detect worsening).

    Returns
    -------
    list[DriftAlert]
    """
    alerts: list[DriftAlert] = []

    # Alert on classification
    if drift_result.classification in ("SIGNIFICANT", "CRITICAL"):
        alerts.append(DriftAlert(
            alert_type="DRIFT_THRESHOLD",
            severity="HIGH",
            message=(
                f"Portfolio drift is {drift_result.classification} "
                f"at {drift_result.total_drift_pct:.2f}%."
            ),
            drift_details={
                "total_drift": drift_result.total_drift_pct,
                "classification": drift_result.classification,
            },
        ))

    # Alert on rebalance needed
    if drift_result.rebalance_needed:
        alerts.append(DriftAlert(
            alert_type="REBALANCE_NEEDED",
            severity="MEDIUM",
            message=(
                f"Rebalance recommended: total drift "
                f"{drift_result.total_drift_pct:.2f}% exceeds "
                f"{REBALANCE_THRESHOLD}% threshold."
            ),
            drift_details={
                "total_drift": drift_result.total_drift_pct,
                "threshold": REBALANCE_THRESHOLD,
                "trade_count": len(drift_result.rebalance_trades),
            },
        ))

    # Alert on large single-position drifts
    for pd in drift_result.position_drifts:
        if pd.abs_drift >= DRIFT_THRESHOLDS["SIGNIFICANT"]:
            alerts.append(DriftAlert(
                alert_type="POSITION_DRIFT",
                severity="HIGH",
                message=(
                    f"{pd.ticker} drift {pd.drift_pct:+.2f}% "
                    f"(target {pd.target_weight:.2f}%, "
                    f"current {pd.current_weight:.2f}%)."
                ),
                drift_details={
                    "ticker": pd.ticker,
                    "drift_pct": pd.drift_pct,
                    "abs_drift": pd.abs_drift,
                },
            ))

    # Detect worsening drift
    if prior_drift is not None:
        if (
            drift_result.total_drift_pct > prior_drift.total_drift_pct
            and drift_result.classification != "MINIMAL"
        ):
            alerts.append(DriftAlert(
                alert_type="DRIFT_WORSENING",
                severity="MEDIUM",
                message=(
                    f"Drift increased from {prior_drift.total_drift_pct:.2f}% "
                    f"to {drift_result.total_drift_pct:.2f}%."
                ),
                drift_details={
                    "prior_drift": prior_drift.total_drift_pct,
                    "current_drift": drift_result.total_drift_pct,
                },
            ))

    return alerts


# ── Full Drift Orchestrator ──────────────────────────────────────────────


def analyze_drift(
    current_weights: dict,
    target_weights: dict,
    positions: list[dict] | None = None,
    target_sector_weights: dict | None = None,
    portfolio_nav: float = 0.0,
) -> DriftResult:
    """Full drift analysis orchestrator.

    Parameters
    ----------
    current_weights : dict
        Mapping ticker -> current weight (percentage).
    target_weights : dict
        Mapping ticker -> target weight (percentage).
    positions : list[dict] | None
        Positions with sector data for sector drift. Optional.
    target_sector_weights : dict | None
        Target sector weights. Optional.
    portfolio_nav : float
        Portfolio NAV for trade sizing. Default 0.

    Returns
    -------
    DriftResult
    """
    position_drifts = compute_position_drift(current_weights, target_weights)
    total_drift = compute_total_drift(position_drifts)
    classification = classify_drift(total_drift)
    rebalance_needed = total_drift > REBALANCE_THRESHOLD

    max_pos_drift = max((d.abs_drift for d in position_drifts), default=0.0)

    # Sector drift
    sector_drifts: list[SectorDrift] = []
    max_sector_drift = 0.0
    if positions and target_sector_weights:
        sector_drifts = compute_sector_drift(positions, target_sector_weights)
        max_sector_drift = max(
            (abs(s.drift_pct) for s in sector_drifts), default=0.0,
        )

    # Rebalance trades
    rebalance_trades: list[dict] = []
    if rebalance_needed and portfolio_nav > 0:
        rebalance_trades = suggest_rebalance_trades(position_drifts, portfolio_nav)

    return DriftResult(
        total_drift_pct=total_drift,
        max_position_drift_pct=round(max_pos_drift, 4),
        max_sector_drift_pct=round(max_sector_drift, 4),
        classification=classification,
        rebalance_needed=rebalance_needed,
        position_drifts=position_drifts,
        sector_drifts=sector_drifts,
        rebalance_trades=rebalance_trades,
    )


# ── Tracking Error ───────────────────────────────────────────────────────


def compute_tracking_error(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """Compute annualized tracking error.

    Parameters
    ----------
    portfolio_returns : list[float]
        Period returns (e.g. daily).
    benchmark_returns : list[float]
        Benchmark returns for same periods.

    Returns
    -------
    float
        Annualized tracking error (assuming 252 trading days).
        Returns 0.0 if fewer than 2 observations.
    """
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return 0.0

    diffs = [portfolio_returns[i] - benchmark_returns[i] for i in range(n)]
    mean_diff = sum(diffs) / n
    variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    std = math.sqrt(variance)

    return round(std * math.sqrt(252), 6)
