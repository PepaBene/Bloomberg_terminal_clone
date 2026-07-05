"""Pillar 4 Phase 3 — What-If / Pre-Trade Impact Analysis Engine.

Pure computation engine for side-by-side current-vs-proposed portfolio
comparison across position weights, risk metrics, factor exposures,
compliance rules, and transaction costs.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_COMMISSION_PER_SHARE = 0.005
DEFAULT_AVG_SPREAD_BPS = 5.0
DEFAULT_MARKET_IMPACT_BPS = 2.0
BPS_DIVISOR = 10_000


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class ProposedTrade:
    """A single proposed trade for what-if analysis."""

    ticker: str
    action: str  # BUY / SELL
    shares: float
    price_per_share: float
    notional_amount: float


@dataclass
class PositionImpact:
    """Side-by-side position impact for a single ticker."""

    ticker: str
    current_weight: float
    proposed_weight: float
    weight_change: float
    current_shares: float
    proposed_shares: float
    current_market_value: float
    proposed_market_value: float


@dataclass
class RiskImpact:
    """Side-by-side risk metric comparison."""

    current_var_95: float
    proposed_var_95: float
    var_change: float
    current_volatility: float
    proposed_volatility: float
    vol_change: float
    current_beta: float
    proposed_beta: float
    beta_change: float


@dataclass
class FactorImpact:
    """Side-by-side factor exposure comparison for a single factor."""

    factor: str
    current_exposure: float
    proposed_exposure: float
    exposure_change: float


@dataclass
class ComplianceImpact:
    """Side-by-side compliance status for a single rule."""

    rule_name: str
    current_status: str  # PASS / WARNING / BREACH / N_A
    proposed_status: str
    breach_introduced: bool
    notes: str


@dataclass
class TransactionCostEstimate:
    """Estimated transaction costs for the proposed trades."""

    total_commission: float
    market_impact_bps: float
    spread_cost: float
    total_cost: float
    cost_pct_of_nav: float


@dataclass
class WhatIfResult:
    """Full what-if analysis result combining all dimensions."""

    portfolio_id: str
    proposed_trades: list[ProposedTrade]
    position_impacts: list[PositionImpact]
    risk_impact: RiskImpact
    factor_impacts: list[FactorImpact]
    compliance_impacts: list[ComplianceImpact]
    transaction_cost: TransactionCostEstimate
    summary: dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Simulate Trades ─────────────────────────────────────────────────────


def simulate_trades(
    positions: list[dict],
    trades: list[dict],
    portfolio_nav: float,
) -> list[PositionImpact]:
    """Apply proposed trades to current positions and compute weight changes.

    Parameters
    ----------
    positions : list[dict]
        Current positions. Each: {ticker, shares, market_value, weight, ...}.
        weight is a percentage (e.g. 10.0 = 10%).
    trades : list[dict]
        Proposed trades. Each: {ticker, action (BUY/SELL), shares,
        price_per_share, ...}.
    portfolio_nav : float
        Current portfolio net asset value.

    Returns
    -------
    list[PositionImpact]
        One entry per affected ticker, sorted by absolute weight change
        descending.
    """
    if portfolio_nav <= 0:
        return []

    # Build a lookup of current positions by ticker
    pos_map: dict[str, dict] = {}
    for p in positions:
        ticker = p.get("ticker", "")
        pos_map[ticker] = {
            "shares": p.get("shares", 0.0),
            "market_value": p.get("market_value", 0.0),
            "weight": p.get("weight", 0.0),
        }

    # Compute trade notionals and build proposed position state
    trade_deltas: dict[str, dict] = {}
    for t in trades:
        ticker = t.get("ticker", "")
        action = t.get("action", "BUY").upper()
        shares = t.get("shares", 0.0)
        price = t.get("price_per_share", 0.0)
        notional = shares * price

        if ticker not in trade_deltas:
            trade_deltas[ticker] = {"shares_delta": 0.0, "notional_delta": 0.0}

        if action == "BUY":
            trade_deltas[ticker]["shares_delta"] += shares
            trade_deltas[ticker]["notional_delta"] += notional
        elif action == "SELL":
            trade_deltas[ticker]["shares_delta"] -= shares
            trade_deltas[ticker]["notional_delta"] -= notional

    # Compute proposed NAV (current NAV + net cash flow from trades)
    total_trade_notional = sum(d["notional_delta"] for d in trade_deltas.values())
    proposed_nav = portfolio_nav + total_trade_notional

    if proposed_nav <= 0:
        proposed_nav = portfolio_nav  # fallback to avoid division by zero

    # Build impacts for all affected tickers
    affected_tickers = set(trade_deltas.keys())
    impacts: list[PositionImpact] = []

    for ticker in affected_tickers:
        current = pos_map.get(ticker, {"shares": 0.0, "market_value": 0.0, "weight": 0.0})
        delta = trade_deltas[ticker]

        current_shares = current["shares"]
        current_mv = current["market_value"]
        current_weight = current["weight"]

        proposed_shares = max(0.0, current_shares + delta["shares_delta"])
        proposed_mv = max(0.0, current_mv + delta["notional_delta"])
        proposed_weight = round(proposed_mv / proposed_nav * 100.0, 4) if proposed_nav > 0 else 0.0
        weight_change = round(proposed_weight - current_weight, 4)

        impacts.append(PositionImpact(
            ticker=ticker,
            current_weight=round(current_weight, 4),
            proposed_weight=proposed_weight,
            weight_change=weight_change,
            current_shares=round(current_shares, 4),
            proposed_shares=round(proposed_shares, 4),
            current_market_value=round(current_mv, 2),
            proposed_market_value=round(proposed_mv, 2),
        ))

    impacts.sort(key=lambda i: -abs(i.weight_change))
    return impacts


# ── Risk Impact ──────────────────────────────────────────────────────────


def estimate_risk_impact(
    current_risk: dict,
    positions: list[dict],
    trades: list[dict],
    individual_vars: dict,
    correlation_matrix: dict,
    portfolio_nav: float,
) -> RiskImpact:
    """Estimate the change in portfolio risk metrics from proposed trades.

    Uses a parametric approximation: proposed VaR is computed from
    individual asset VaRs and pairwise correlations using the
    variance-covariance approach.

    Parameters
    ----------
    current_risk : dict
        Current risk metrics: {var_95, volatility, beta, ...}.
    positions : list[dict]
        Current positions: {ticker, shares, market_value, weight, ...}.
    trades : list[dict]
        Proposed trades: {ticker, action, shares, price_per_share, ...}.
    individual_vars : dict
        Per-ticker individual VaR (95%): {ticker: float, ...}.
        Values should be in dollar terms or proportional to market value.
    correlation_matrix : dict
        Pairwise correlations: {(ticker_a, ticker_b): float, ...}
        or {ticker_a: {ticker_b: float, ...}, ...}.
    portfolio_nav : float
        Current portfolio net asset value.

    Returns
    -------
    RiskImpact
    """
    current_var = current_risk.get("var_95", 0.0)
    current_vol = current_risk.get("volatility", 0.0)
    current_beta = current_risk.get("beta", 1.0)

    # If we have no meaningful inputs, return zero-change result
    if not positions and not trades:
        return RiskImpact(
            current_var_95=round(current_var, 6),
            proposed_var_95=round(current_var, 6),
            var_change=0.0,
            current_volatility=round(current_vol, 6),
            proposed_volatility=round(current_vol, 6),
            vol_change=0.0,
            current_beta=round(current_beta, 4),
            proposed_beta=round(current_beta, 4),
            beta_change=0.0,
        )

    # Build proposed weight map
    pos_map: dict[str, float] = {}
    beta_map: dict[str, float] = {}
    vol_map: dict[str, float] = {}

    for p in positions:
        ticker = p.get("ticker", "")
        pos_map[ticker] = p.get("weight", 0.0) / 100.0  # convert pct to decimal
        beta_map[ticker] = p.get("beta", 1.0)
        vol_map[ticker] = p.get("volatility", current_vol)

    # Apply trade deltas to weights
    if portfolio_nav > 0:
        for t in trades:
            ticker = t.get("ticker", "")
            action = t.get("action", "BUY").upper()
            shares = t.get("shares", 0.0)
            price = t.get("price_per_share", 0.0)
            notional = shares * price
            weight_delta = notional / portfolio_nav

            if ticker not in pos_map:
                pos_map[ticker] = 0.0
            if ticker not in beta_map:
                beta_map[ticker] = t.get("beta", 1.0)
            if ticker not in vol_map:
                vol_map[ticker] = t.get("volatility", current_vol)

            if action == "BUY":
                pos_map[ticker] = pos_map[ticker] + weight_delta
            elif action == "SELL":
                pos_map[ticker] = max(0.0, pos_map[ticker] - weight_delta)

    proposed_weights = pos_map

    # ── Proposed Beta: weighted average ──
    total_weight = sum(proposed_weights.values())
    if total_weight > 0:
        proposed_beta = sum(
            w * beta_map.get(t, 1.0)
            for t, w in proposed_weights.items()
        ) / total_weight
    else:
        proposed_beta = current_beta

    # ── Proposed Volatility: weighted average approximation ──
    if total_weight > 0:
        proposed_vol = sum(
            w * vol_map.get(t, current_vol)
            for t, w in proposed_weights.items()
        ) / total_weight
    else:
        proposed_vol = current_vol

    # ── Proposed VaR: variance-covariance approximation ──
    tickers = list(proposed_weights.keys())
    proposed_var = _compute_parametric_var(
        tickers, proposed_weights, individual_vars, correlation_matrix, portfolio_nav,
    )

    # Fallback: if parametric VaR could not be computed, scale current VaR
    if proposed_var == 0.0 and current_var > 0.0:
        vol_ratio = proposed_vol / current_vol if current_vol > 0 else 1.0
        proposed_var = current_var * vol_ratio

    return RiskImpact(
        current_var_95=round(current_var, 6),
        proposed_var_95=round(proposed_var, 6),
        var_change=round(proposed_var - current_var, 6),
        current_volatility=round(current_vol, 6),
        proposed_volatility=round(proposed_vol, 6),
        vol_change=round(proposed_vol - current_vol, 6),
        current_beta=round(current_beta, 4),
        proposed_beta=round(proposed_beta, 4),
        beta_change=round(proposed_beta - current_beta, 4),
    )


def _compute_parametric_var(
    tickers: list[str],
    weights: dict[str, float],
    individual_vars: dict,
    correlation_matrix: dict,
    portfolio_nav: float,
) -> float:
    """Compute parametric portfolio VaR using variance-covariance method.

    Parameters
    ----------
    tickers : list[str]
    weights : dict[str, float]
        Decimal weights (not percentages).
    individual_vars : dict
        Per-ticker VaR values: {ticker: float}.
    correlation_matrix : dict
        Nested dict {ticker_a: {ticker_b: corr}} or flat
        {(ticker_a, ticker_b): corr}.
    portfolio_nav : float

    Returns
    -------
    float
        Portfolio VaR estimate. Returns 0.0 if insufficient data.
    """
    if not tickers or not individual_vars:
        return 0.0

    # Filter to tickers that have individual VaR data
    valid_tickers = [t for t in tickers if t in individual_vars]
    if not valid_tickers:
        return 0.0

    n = len(valid_tickers)
    w_var = []
    for t in valid_tickers:
        w = weights.get(t, 0.0)
        v = individual_vars.get(t, 0.0)
        w_var.append(w * v)

    # Portfolio variance = sum_i sum_j (w_i * var_i) * (w_j * var_j) * corr_ij
    portfolio_variance = 0.0
    for i in range(n):
        for j in range(n):
            corr = _get_correlation(
                valid_tickers[i], valid_tickers[j], correlation_matrix,
            )
            portfolio_variance += w_var[i] * w_var[j] * corr

    if portfolio_variance < 0:
        return 0.0

    return math.sqrt(portfolio_variance)


def _get_correlation(
    ticker_a: str,
    ticker_b: str,
    correlation_matrix: dict,
) -> float:
    """Look up pairwise correlation from nested or flat dict.

    Parameters
    ----------
    ticker_a : str
    ticker_b : str
    correlation_matrix : dict
        Either {ticker_a: {ticker_b: float}} or
        {(ticker_a, ticker_b): float}.

    Returns
    -------
    float
        Correlation coefficient. Returns 1.0 if same ticker,
        0.0 if not found.
    """
    if ticker_a == ticker_b:
        return 1.0

    # Try nested dict format
    if ticker_a in correlation_matrix and isinstance(correlation_matrix[ticker_a], dict):
        return correlation_matrix[ticker_a].get(ticker_b, 0.0)

    # Try flat tuple-key format
    if (ticker_a, ticker_b) in correlation_matrix:
        return correlation_matrix[(ticker_a, ticker_b)]
    if (ticker_b, ticker_a) in correlation_matrix:
        return correlation_matrix[(ticker_b, ticker_a)]

    return 0.0


# ── Factor Impact ────────────────────────────────────────────────────────


def estimate_factor_impact(
    positions: list[dict],
    trades: list[dict],
    factor_data: dict,
    portfolio_nav: float | None = None,
) -> list[FactorImpact]:
    """Estimate change in factor exposures from proposed trades.

    Parameters
    ----------
    positions : list[dict]
        Current positions: {ticker, weight, ...}. Weight in percentage.
    trades : list[dict]
        Proposed trades: {ticker, action, shares, price_per_share, weight_pct?}.
    factor_data : dict
        Per-ticker factor loadings:
        {ticker: {factor_name: loading, ...}, ...}.
    portfolio_nav : float | None
        Optional portfolio NAV used to translate trade notional into a weight
        delta when ``weight_pct`` is not supplied on the trade.

    Returns
    -------
    list[FactorImpact]
        One entry per factor, sorted by absolute exposure change
        descending.
    """
    if not factor_data:
        return []

    # Gather all factor names
    all_factors: set[str] = set()
    for loadings in factor_data.values():
        if isinstance(loadings, dict):
            all_factors.update(loadings.keys())

    if not all_factors:
        return []

    # Current weighted factor exposures
    current_weights: dict[str, float] = {}
    total_current_weight = 0.0
    for p in positions:
        ticker = p.get("ticker", "")
        w = p.get("weight", 0.0)
        current_weights[ticker] = w
        total_current_weight += w

    current_exposures = _weighted_factor_exposures(
        current_weights, factor_data, total_current_weight,
    )

    # Proposed weights: apply trade deltas. Prefer an explicit weight_pct on
    # the trade. When absent, derive the weight delta from notional / NAV;
    # the engine accepts a portfolio_nav argument when available, otherwise
    # we approximate using the implied NAV (sum of current weights ≈ 1.0).
    proposed_weights = dict(current_weights)
    total_trade_weight = 0.0
    implied_nav = portfolio_nav if portfolio_nav and portfolio_nav > 0 else None
    for t in trades:
        ticker = t.get("ticker", "")
        action = t.get("action", "BUY").upper()
        shares = float(t.get("shares", 0.0) or 0.0)
        price = float(t.get("price_per_share", 0.0) or 0.0)
        notional = shares * price
        explicit_weight = t.get("weight_pct")
        if explicit_weight is not None:
            weight_delta = float(explicit_weight)
        elif implied_nav and notional > 0:
            weight_delta = notional / implied_nav
        elif total_current_weight > 0 and notional > 0:
            # Without a NAV we can only approximate: treat each unit of
            # current weight as proportional to its notional contribution.
            weight_delta = notional / max(total_current_weight, 1.0)
        else:
            weight_delta = 0.0

        if ticker not in proposed_weights:
            proposed_weights[ticker] = 0.0

        if action == "BUY":
            proposed_weights[ticker] += weight_delta
            total_trade_weight += weight_delta
        elif action == "SELL":
            proposed_weights[ticker] = max(0.0, proposed_weights[ticker] - weight_delta)
            total_trade_weight -= weight_delta

    total_proposed_weight = total_current_weight + total_trade_weight

    proposed_exposures = _weighted_factor_exposures(
        proposed_weights, factor_data, total_proposed_weight,
    )

    # Build impacts
    impacts: list[FactorImpact] = []
    for factor in sorted(all_factors):
        current_exp = current_exposures.get(factor, 0.0)
        proposed_exp = proposed_exposures.get(factor, 0.0)
        change = proposed_exp - current_exp

        impacts.append(FactorImpact(
            factor=factor,
            current_exposure=round(current_exp, 6),
            proposed_exposure=round(proposed_exp, 6),
            exposure_change=round(change, 6),
        ))

    impacts.sort(key=lambda f: -abs(f.exposure_change))
    return impacts


def _weighted_factor_exposures(
    weights: dict[str, float],
    factor_data: dict,
    total_weight: float,
) -> dict[str, float]:
    """Compute weighted-average factor exposures.

    Parameters
    ----------
    weights : dict[str, float]
        Mapping ticker -> weight (percentage).
    factor_data : dict
        Mapping ticker -> {factor: loading}.
    total_weight : float
        Sum of all weights for normalization.

    Returns
    -------
    dict[str, float]
        Mapping factor -> weighted exposure.
    """
    exposures: dict[str, float] = {}

    if total_weight <= 0:
        return exposures

    for ticker, w in weights.items():
        if ticker not in factor_data:
            continue
        loadings = factor_data[ticker]
        if not isinstance(loadings, dict):
            continue
        normalized_w = w / total_weight
        for factor, loading in loadings.items():
            exposures[factor] = exposures.get(factor, 0.0) + normalized_w * loading

    return exposures


# ── Compliance Impact ────────────────────────────────────────────────────


def check_compliance_impact(
    positions: list[dict],
    trades: list[dict],
    rules: list[dict],
    context: dict,
) -> list[ComplianceImpact]:
    """Check compliance status before and after proposed trades.

    Evaluates each rule against current positions and against the
    simulated post-trade positions, then reports any new breaches.

    Parameters
    ----------
    positions : list[dict]
        Current positions: {ticker, weight, sector, ...}.
        Weight in percentage.
    trades : list[dict]
        Proposed trades: {ticker, action, shares, price_per_share,
        weight_pct?, sector?, ...}.
    rules : list[dict]
        Compliance rules: {rule_name, rule_type, max_weight?,
        max_sector_weight?, ...}.
    context : dict
        Additional compliance context: {scores?, valuations?,
        risk_data?}.

    Returns
    -------
    list[ComplianceImpact]
        One entry per rule, sorted with breach-introducing rules first.
    """
    if not rules:
        return []

    # Build proposed positions by applying trades
    proposed_positions = _apply_trades_to_positions(positions, trades)

    impacts: list[ComplianceImpact] = []

    for rule in rules:
        rule_name = rule.get("rule_name", "Unknown Rule")
        rule_type = rule.get("rule_type", "CUSTOM")

        current_status = _evaluate_single_rule(positions, rule, context)
        proposed_status = _evaluate_single_rule(proposed_positions, rule, context)

        # A breach is "introduced" if current is not BREACH but proposed is
        breach_introduced = (
            current_status != "BREACH" and proposed_status == "BREACH"
        )

        if breach_introduced:
            notes = f"Trade would introduce a {rule_type} breach."
        elif current_status == "BREACH" and proposed_status != "BREACH":
            notes = f"Trade would resolve existing {rule_type} breach."
        elif current_status == proposed_status:
            notes = f"No change in compliance status ({current_status})."
        else:
            notes = f"Status changes from {current_status} to {proposed_status}."

        impacts.append(ComplianceImpact(
            rule_name=rule_name,
            current_status=current_status,
            proposed_status=proposed_status,
            breach_introduced=breach_introduced,
            notes=notes,
        ))

    # Sort: breach-introducing first, then by rule name
    impacts.sort(key=lambda c: (not c.breach_introduced, c.rule_name))
    return impacts


def _apply_trades_to_positions(
    positions: list[dict],
    trades: list[dict],
) -> list[dict]:
    """Apply trade weight deltas to positions for compliance simulation.

    Parameters
    ----------
    positions : list[dict]
    trades : list[dict]

    Returns
    -------
    list[dict]
        New positions list with adjusted weights.
    """
    # Deep copy positions
    pos_map: dict[str, dict] = {}
    for p in positions:
        ticker = p.get("ticker", "")
        pos_map[ticker] = dict(p)

    for t in trades:
        ticker = t.get("ticker", "")
        action = t.get("action", "BUY").upper()
        weight_delta = t.get("weight_pct", 0.0)

        if ticker not in pos_map:
            pos_map[ticker] = {
                "ticker": ticker,
                "weight": 0.0,
                "sector": t.get("sector", "Unknown"),
            }

        if action == "BUY":
            pos_map[ticker]["weight"] = pos_map[ticker].get("weight", 0.0) + weight_delta
        elif action == "SELL":
            pos_map[ticker]["weight"] = max(
                0.0, pos_map[ticker].get("weight", 0.0) - weight_delta,
            )

    # Remove zero-weight positions
    return [p for p in pos_map.values() if p.get("weight", 0.0) > 0.0]


def _evaluate_single_rule(
    positions: list[dict],
    rule: dict,
    context: dict,
) -> str:
    """Evaluate a single compliance rule against positions.

    Parameters
    ----------
    positions : list[dict]
    rule : dict
    context : dict

    Returns
    -------
    str
        Status: PASS / WARNING / BREACH / N_A.
    """
    rule_type = rule.get("rule_type", "CUSTOM")

    if rule_type == "POSITION_LIMIT":
        max_weight = rule.get("max_weight", 100.0)
        if not positions:
            return "N_A"
        for p in positions:
            if p.get("weight", 0.0) > max_weight:
                return "BREACH"
        return "PASS"

    elif rule_type == "SECTOR_LIMIT":
        max_sector_weight = rule.get("max_sector_weight", 100.0)
        if not positions:
            return "N_A"
        sector_weights: dict[str, float] = {}
        for p in positions:
            sector = p.get("sector", "Unknown")
            sector_weights[sector] = (
                sector_weights.get(sector, 0.0) + p.get("weight", 0.0)
            )
        for w in sector_weights.values():
            if w > max_sector_weight:
                return "BREACH"
        return "PASS"

    elif rule_type == "RISK":
        risk_data = context.get("risk_data", {})
        metric = rule.get("metric", "var_95")
        threshold = rule.get("threshold", 0.0)
        comparison = rule.get("comparison", "LTE").upper()
        if metric not in risk_data:
            return "N_A"
        value = risk_data[metric]
        if comparison == "LTE" and value <= threshold:
            return "PASS"
        elif comparison == "LT" and value < threshold:
            return "PASS"
        elif comparison == "GTE" and value >= threshold:
            return "PASS"
        elif comparison == "GT" and value > threshold:
            return "PASS"
        return "BREACH"

    return "N_A"


# ── Transaction Cost Estimate ────────────────────────────────────────────


def estimate_transaction_costs(
    trades: list[dict],
    portfolio_nav: float,
    avg_spread_bps: float = DEFAULT_AVG_SPREAD_BPS,
    commission_per_share: float = DEFAULT_COMMISSION_PER_SHARE,
    market_impact_bps: float = DEFAULT_MARKET_IMPACT_BPS,
) -> TransactionCostEstimate:
    """Estimate total transaction costs for proposed trades.

    Parameters
    ----------
    trades : list[dict]
        Proposed trades: {ticker, action, shares, price_per_share, ...}.
    portfolio_nav : float
        Portfolio net asset value for cost-as-pct-of-NAV calculation.
    avg_spread_bps : float
        Average bid-ask spread in basis points. Default 5.0.
    commission_per_share : float
        Commission per share in currency units. Default 0.005.
    market_impact_bps : float
        Estimated market impact in basis points. Default 2.0.

    Returns
    -------
    TransactionCostEstimate
    """
    if not trades:
        return TransactionCostEstimate(
            total_commission=0.0,
            market_impact_bps=0.0,
            spread_cost=0.0,
            total_cost=0.0,
            cost_pct_of_nav=0.0,
        )

    total_commission = 0.0
    total_notional = 0.0
    total_shares = 0.0

    for t in trades:
        shares = t.get("shares", 0.0)
        price = t.get("price_per_share", 0.0)
        notional = shares * price

        total_commission += shares * commission_per_share
        total_notional += notional
        total_shares += shares

    spread_cost = round(total_notional * avg_spread_bps / BPS_DIVISOR, 2)
    impact_cost = round(total_notional * market_impact_bps / BPS_DIVISOR, 2)
    total_commission = round(total_commission, 2)

    total_cost = round(total_commission + spread_cost + impact_cost, 2)
    cost_pct = round(total_cost / portfolio_nav * 100.0, 6) if portfolio_nav > 0 else 0.0

    return TransactionCostEstimate(
        total_commission=total_commission,
        market_impact_bps=market_impact_bps,
        spread_cost=spread_cost,
        total_cost=total_cost,
        cost_pct_of_nav=cost_pct,
    )


# ── Full What-If Orchestrator ────────────────────────────────────────────


def run_whatif_analysis(
    portfolio_id: str,
    positions: list[dict],
    proposed_trades: list[dict],
    portfolio_nav: float,
    risk_data: dict,
    factor_data: dict,
    compliance_rules: list[dict],
    compliance_context: dict,
    individual_vars: dict,
    correlation_matrix: dict,
) -> WhatIfResult:
    """Run a full what-if / pre-trade impact analysis.

    Orchestrates all sub-analyses: position impact, risk impact,
    factor exposure changes, compliance checks, and transaction
    cost estimation.

    Parameters
    ----------
    portfolio_id : str
        Portfolio identifier.
    positions : list[dict]
        Current positions: {ticker, shares, market_value, weight,
        sector?, beta?, volatility?, ...}.
    proposed_trades : list[dict]
        Trades to simulate: {ticker, action (BUY/SELL), shares,
        price_per_share, weight_pct?, sector?, ...}.
    portfolio_nav : float
        Current portfolio net asset value.
    risk_data : dict
        Current risk metrics: {var_95, volatility, beta, ...}.
    factor_data : dict
        Per-ticker factor loadings: {ticker: {factor: loading}}.
    compliance_rules : list[dict]
        Compliance rules to evaluate.
    compliance_context : dict
        Additional compliance context: {scores?, valuations?,
        risk_data?}.
    individual_vars : dict
        Per-ticker VaR values: {ticker: float}.
    correlation_matrix : dict
        Pairwise correlations for VaR computation.

    Returns
    -------
    WhatIfResult
        Complete what-if analysis with all dimensions populated.
    """
    # Normalize trades to ProposedTrade dataclass instances
    trade_objects: list[ProposedTrade] = []
    for t in proposed_trades:
        if isinstance(t, ProposedTrade):
            trade_objects.append(t)
        else:
            shares = t.get("shares", 0.0)
            price = t.get("price_per_share", 0.0)
            trade_objects.append(ProposedTrade(
                ticker=t.get("ticker", ""),
                action=t.get("action", "BUY").upper(),
                shares=shares,
                price_per_share=price,
                notional_amount=round(shares * price, 2),
            ))

    # Convert to dicts for sub-functions that expect dict inputs
    trade_dicts = [
        {
            "ticker": t.ticker,
            "action": t.action,
            "shares": t.shares,
            "price_per_share": t.price_per_share,
            "notional_amount": t.notional_amount,
        }
        for t in trade_objects
    ]

    # 1. Position impacts
    position_impacts = simulate_trades(positions, trade_dicts, portfolio_nav)

    # 2. Risk impact
    risk_impact = estimate_risk_impact(
        current_risk=risk_data,
        positions=positions,
        trades=trade_dicts,
        individual_vars=individual_vars,
        correlation_matrix=correlation_matrix,
        portfolio_nav=portfolio_nav,
    )

    # 3. Factor impacts
    factor_impacts = estimate_factor_impact(positions, trade_dicts, factor_data)

    # 4. Compliance impacts
    compliance_impacts = check_compliance_impact(
        positions, trade_dicts, compliance_rules, compliance_context,
    )

    # 5. Transaction costs
    transaction_cost = estimate_transaction_costs(trade_dicts, portfolio_nav)

    # 6. Build summary
    breaches_introduced = sum(1 for c in compliance_impacts if c.breach_introduced)
    total_trade_notional = sum(t.notional_amount for t in trade_objects)

    summary = {
        "total_trades": len(trade_objects),
        "total_notional": round(total_trade_notional, 2),
        "positions_affected": len(position_impacts),
        "var_change_pct": round(risk_impact.var_change, 6),
        "beta_change": round(risk_impact.beta_change, 4),
        "compliance_breaches_introduced": breaches_introduced,
        "estimated_total_cost": transaction_cost.total_cost,
        "cost_pct_of_nav": transaction_cost.cost_pct_of_nav,
    }

    return WhatIfResult(
        portfolio_id=portfolio_id,
        proposed_trades=trade_objects,
        position_impacts=position_impacts,
        risk_impact=risk_impact,
        factor_impacts=factor_impacts,
        compliance_impacts=compliance_impacts,
        transaction_cost=transaction_cost,
        summary=summary,
    )
