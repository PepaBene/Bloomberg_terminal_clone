"""Pillar 4 Phase 3 — Portfolio Risk: Risk Calculation Engine.

Pure computation engine for Value-at-Risk, concentration analysis,
factor exposure decomposition, and stress testing.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── Constants ─────────────────────────────────────────────────────────

CONFIDENCE_LEVELS: dict[str, float] = {
    "95": 1.645,
    "99": 2.326,
}

HISTORICAL_SCENARIOS: dict[str, dict] = {
    "GFC_2008": {
        "label": "2008 Global Financial Crisis",
        "equity_shock": -0.55,
        "rate_shock_bps": -200,
        "spread_shock_bps": 400,
        "recovery_months": 48,
    },
    "COVID_2020": {
        "label": "COVID-19 Crash",
        "equity_shock": -0.34,
        "rate_shock_bps": -150,
        "spread_shock_bps": 350,
        "recovery_months": 5,
    },
    "RATE_SHOCK_2022": {
        "label": "2022 Rate Shock",
        "equity_shock": -0.25,
        "rate_shock_bps": 300,
        "spread_shock_bps": 100,
        "recovery_months": 12,
    },
    "DOTCOM_2000": {
        "label": "Dot-Com Bust",
        "equity_shock": -0.49,
        "rate_shock_bps": -300,
        "spread_shock_bps": 200,
        "recovery_months": 30,
    },
}

CONCENTRATION_THRESHOLDS: dict[str, int] = {
    "DIVERSIFIED": 500,
    "MODERATE": 1500,
}

FACTORS: list[str] = ["value", "growth", "momentum", "quality", "size", "low_vol"]

# Default number of standard deviations a factor exposure must move from its
# historical mean before being flagged as "drift" (an unintended bet vs. the
# portfolio's own history). Exposed as a `compute_factor_exposures` parameter
# so callers can tune sensitivity instead of it being a silent hardcode.
DEFAULT_DRIFT_ZSCORE_THRESHOLD = 2.0


# ── Dataclasses ───────────────────────────────────────────────────────


@dataclass
class VaRResult:
    """Full Value-at-Risk decomposition for a portfolio."""

    var_1d_95: float
    var_1d_99: float
    var_10d_95: float
    var_10d_99: float
    undiversified_var: float
    diversification_ratio: float
    marginal_var: dict  # {ticker: float}
    component_var: dict  # {ticker: float}
    incremental_var: dict  # {ticker: float}
    portfolio_nav: float


@dataclass
class ConcentrationResult:
    """Portfolio concentration analysis across multiple dimensions."""

    hhi_position: float
    hhi_sector: float
    hhi_industry: float
    largest_position_weight: float
    top_5_weight: float
    top_10_weight: float
    effective_num_positions: float
    classification: str
    sector_detail: list[dict]
    industry_detail: list[dict]
    geographic_detail: list[dict]
    flags: list[str]


@dataclass
class FactorExposureResult:
    """Factor exposure decomposition relative to benchmark."""

    portfolio_exposures: dict  # {factor: float}
    benchmark_exposures: dict
    active_exposures: dict
    factor_contributions: dict
    unintended_flags: list[dict]


@dataclass
class StressTestResult:
    """Result of a stress-test scenario applied to a portfolio."""

    scenario_name: str
    scenario_type: str
    total_pnl_dollar: float
    total_pnl_percent: float
    max_drawdown_pct: float
    recovery_time_months: float
    per_position_pnl: dict  # {ticker: {pnl_dollar, pnl_pct}}
    worst_positions: list[dict]


# ── VaR Calculations ──────────────────────────────────────────────────


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize weights so |weight| sums to 1.0 when caller passed dollar amounts.

    The variance-covariance VaR formula assumes weights are fractions of NAV.
    Callers occasionally pass raw dollar amounts; without rescaling the
    output is off by orders of magnitude. Always rescale by the absolute
    sum (exact normalization) rather than only when "far" from 1.0 — for
    weights that already sum to ~1.0 this is a no-op (division by ~1.0), so
    there's no downside to normalizing unconditionally, and it avoids a
    tolerance band silently letting slightly-off inputs (e.g. 1.03) through
    unnormalized. Long-short books, where signed weights can sum near 0,
    still scale sensibly since we divide by the *absolute* sum.
    """
    if not weights:
        return {}
    abs_sum = sum(abs(w) for w in weights.values())
    if abs_sum == 0.0:
        return dict(weights)
    return {t: w / abs_sum for t, w in weights.items()}


def _portfolio_var_from_weights(
    weights: dict[str, float],
    individual_vars: dict[str, float],
    correlation_matrix: dict[str, dict[str, float]],
) -> float:
    """Compute diversified portfolio VaR using variance-covariance method.

    portfolio_var = sqrt( w^T * Sigma * w )
    where Sigma_ij = var_i * var_j * rho_ij

    Weights are taken as-is here so that perturbations used by the marginal
    and incremental VaR helpers behave correctly. Public entry points that
    accept caller-supplied weights normalize them first via
    ``_normalize_weights``.
    """
    tickers = sorted(weights.keys())
    if not tickers:
        return 0.0

    variance = 0.0
    for i, ti in enumerate(tickers):
        for j, tj in enumerate(tickers):
            wi = weights[ti]
            wj = weights[tj]
            vi = individual_vars.get(ti, 0.0)
            vj = individual_vars.get(tj, 0.0)
            rho = correlation_matrix.get(ti, {}).get(tj, 1.0 if ti == tj else 0.0)
            variance += wi * wj * vi * vj * rho

    return math.sqrt(max(variance, 0.0))


def compute_undiversified_var(
    weights: dict[str, float],
    individual_vars: dict[str, float],
) -> float:
    """Compute undiversified VaR: sum of weighted individual VaRs.

    Assumes perfect correlation (rho = 1) among all positions.
    """
    return sum(
        abs(weights.get(t, 0.0)) * individual_vars.get(t, 0.0)
        for t in weights
    )


def compute_component_var(
    weights: dict[str, float],
    individual_vars: dict[str, float],
    correlation_matrix: dict[str, dict[str, float]],
    portfolio_var: float,
) -> dict[str, float]:
    """Compute component VaR per position.

    Component VaR_i = w_i * (sum_j w_j * var_i * var_j * rho_ij) / portfolio_var

    Component VaRs sum to portfolio VaR.
    """
    if portfolio_var == 0.0:
        return {t: 0.0 for t in weights}

    tickers = sorted(weights.keys())
    result: dict[str, float] = {}

    for ti in tickers:
        wi = weights[ti]
        vi = individual_vars.get(ti, 0.0)
        marginal_contrib = 0.0
        for tj in tickers:
            wj = weights[tj]
            vj = individual_vars.get(tj, 0.0)
            rho = correlation_matrix.get(ti, {}).get(tj, 1.0 if ti == tj else 0.0)
            marginal_contrib += wj * vi * vj * rho
        result[ti] = wi * marginal_contrib / portfolio_var

    return result


def compute_marginal_var(
    weights: dict[str, float],
    individual_vars: dict[str, float],
    correlation_matrix: dict[str, dict[str, float]],
    portfolio_var: float,
    delta: float = 0.01,
) -> dict[str, float]:
    """Compute marginal VaR: sensitivity of portfolio VaR to weight changes.

    Marginal VaR_i = (VaR(w + delta*e_i) - VaR(w)) / delta
    """
    result: dict[str, float] = {}

    for ticker in weights:
        shifted = dict(weights)
        shifted[ticker] = shifted[ticker] + delta
        var_shifted = _portfolio_var_from_weights(
            shifted, individual_vars, correlation_matrix,
        )
        result[ticker] = (var_shifted - portfolio_var) / delta

    return result


def compute_incremental_var(
    weights: dict[str, float],
    individual_vars: dict[str, float],
    correlation_matrix: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Compute incremental VaR: portfolio VaR without each position.

    Incremental VaR_i = VaR(full) - VaR(without i)
    Positive means the position adds risk; negative means it hedges.
    """
    full_var = _portfolio_var_from_weights(
        weights, individual_vars, correlation_matrix,
    )
    result: dict[str, float] = {}

    for ticker in weights:
        reduced = {t: w for t, w in weights.items() if t != ticker}
        if not reduced:
            result[ticker] = full_var
        else:
            var_without = _portfolio_var_from_weights(
                reduced, individual_vars, correlation_matrix,
            )
            result[ticker] = full_var - var_without

    return result


def calculate_portfolio_var(
    weights: dict[str, float],
    individual_vars: dict[str, float],
    correlation_matrix: dict[str, dict[str, float]],
    portfolio_nav: float,
) -> VaRResult:
    """Full VaR calculation with component, marginal, and incremental decomposition.

    Parameters
    ----------
    weights : dict
        {ticker: weight} where weight is decimal (e.g. 0.20 for 20%).
    individual_vars : dict
        {ticker: 1-day 95% VaR as decimal} for each position.
    correlation_matrix : dict
        {ticker_i: {ticker_j: correlation}}.
    portfolio_nav : float
        Total portfolio value in dollars.

    Returns
    -------
    VaRResult
        Complete VaR decomposition.
    """
    # Normalize at the entry point so callers passing dollar amounts still
    # get a correct answer. Internal helpers operate on the normalized dict.
    weights = _normalize_weights(weights)

    # 1-day 95% diversified VaR
    var_1d_95 = _portfolio_var_from_weights(
        weights, individual_vars, correlation_matrix,
    )

    # Scale to 99% using z-score ratio
    scale_99 = CONFIDENCE_LEVELS["99"] / CONFIDENCE_LEVELS["95"]
    var_1d_99 = var_1d_95 * scale_99

    # Scale to 10-day using sqrt(10) rule
    sqrt_10 = math.sqrt(10)
    var_10d_95 = var_1d_95 * sqrt_10
    var_10d_99 = var_1d_99 * sqrt_10

    # Undiversified VaR
    undiverse = compute_undiversified_var(weights, individual_vars)

    # Diversification ratio
    div_ratio = (var_1d_95 / undiverse) if undiverse > 0.0 else 1.0

    # Decompositions
    comp = compute_component_var(weights, individual_vars, correlation_matrix, var_1d_95)
    marg = compute_marginal_var(weights, individual_vars, correlation_matrix, var_1d_95)
    incr = compute_incremental_var(weights, individual_vars, correlation_matrix)

    return VaRResult(
        var_1d_95=var_1d_95,
        var_1d_99=var_1d_99,
        var_10d_95=var_10d_95,
        var_10d_99=var_10d_99,
        undiversified_var=undiverse,
        diversification_ratio=div_ratio,
        marginal_var=marg,
        component_var=comp,
        incremental_var=incr,
        portfolio_nav=portfolio_nav,
    )


# ── Concentration Analysis ────────────────────────────────────────────


def compute_hhi(weights: list[float]) -> float:
    """Compute Herfindahl-Hirschman Index: sum of squared weights * 10000.

    Weights should be in decimal form (e.g. 0.10 for 10%).
    """
    return sum(w * w for w in weights) * 10000.0


def classify_concentration(hhi: float) -> str:
    """Classify portfolio concentration based on HHI thresholds.

    < 500  -> DIVERSIFIED
    500-1500 -> MODERATE
    > 1500 -> CONCENTRATED
    """
    if hhi < CONCENTRATION_THRESHOLDS["DIVERSIFIED"]:
        return "DIVERSIFIED"
    elif hhi <= CONCENTRATION_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    else:
        return "CONCENTRATED"


def analyze_concentration(positions: list[dict]) -> ConcentrationResult:
    """Analyze portfolio concentration at position, sector, and industry level.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, sector, industry, country, market_value, ...}.
        weight should be decimal (e.g. 0.10 for 10%).

    Returns
    -------
    ConcentrationResult
        Multi-dimensional concentration analysis with flags.
    """
    if not positions:
        return ConcentrationResult(
            hhi_position=0.0,
            hhi_sector=0.0,
            hhi_industry=0.0,
            largest_position_weight=0.0,
            top_5_weight=0.0,
            top_10_weight=0.0,
            effective_num_positions=0.0,
            classification="DIVERSIFIED",
            sector_detail=[],
            industry_detail=[],
            geographic_detail=[],
            flags=[],
        )

    # Position-level weights
    pos_weights = [p.get("weight", 0.0) for p in positions]
    pos_weights_sorted = sorted(pos_weights, reverse=True)

    hhi_position = compute_hhi(pos_weights)

    # Sector aggregation
    sector_map: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        sector_map[sector] = sector_map.get(sector, 0.0) + p.get("weight", 0.0)

    sector_weights = list(sector_map.values())
    hhi_sector = compute_hhi(sector_weights)
    sector_detail = sorted(
        [{"sector": s, "weight": w, "pct": w * 100.0} for s, w in sector_map.items()],
        key=lambda x: -x["weight"],
    )

    # Industry aggregation
    industry_map: dict[str, float] = {}
    for p in positions:
        industry = p.get("industry", "Unknown")
        industry_map[industry] = industry_map.get(industry, 0.0) + p.get("weight", 0.0)

    industry_weights = list(industry_map.values())
    hhi_industry = compute_hhi(industry_weights)
    industry_detail = sorted(
        [{"industry": i, "weight": w, "pct": w * 100.0} for i, w in industry_map.items()],
        key=lambda x: -x["weight"],
    )

    # Geographic aggregation
    geo_map: dict[str, float] = {}
    for p in positions:
        country = p.get("country", "Unknown")
        geo_map[country] = geo_map.get(country, 0.0) + p.get("weight", 0.0)

    geographic_detail = sorted(
        [{"country": c, "weight": w, "pct": w * 100.0} for c, w in geo_map.items()],
        key=lambda x: -x["weight"],
    )

    # Top-N weights
    largest_weight = pos_weights_sorted[0] if pos_weights_sorted else 0.0
    top_5 = sum(pos_weights_sorted[:5])
    top_10 = sum(pos_weights_sorted[:10])

    # Effective number of positions = 10000 / HHI
    eff_positions = (10000.0 / hhi_position) if hhi_position > 0.0 else 0.0

    classification = classify_concentration(hhi_position)

    # Flags
    flags: list[str] = []
    if largest_weight > 0.20:
        flags.append(f"Single position exceeds 20%: {largest_weight:.1%}")
    if top_5 > 0.60:
        flags.append(f"Top 5 positions exceed 60%: {top_5:.1%}")
    if hhi_sector > 2500:
        flags.append(f"Sector HHI is highly concentrated: {hhi_sector:.0f}")
    if any(w > 0.40 for w in sector_weights):
        over_sector = [s for s, w in sector_map.items() if w > 0.40]
        flags.append(f"Sector(s) over 40%: {', '.join(over_sector)}")
    if len(positions) < 5:
        flags.append(f"Very few positions: {len(positions)}")

    return ConcentrationResult(
        hhi_position=hhi_position,
        hhi_sector=hhi_sector,
        hhi_industry=hhi_industry,
        largest_position_weight=largest_weight,
        top_5_weight=top_5,
        top_10_weight=top_10,
        effective_num_positions=eff_positions,
        classification=classification,
        sector_detail=sector_detail,
        industry_detail=industry_detail,
        geographic_detail=geographic_detail,
        flags=flags,
    )


# ── Factor Exposure ───────────────────────────────────────────────────


def compute_factor_exposures(
    positions: list[dict],
    benchmark_positions: list[dict] | None = None,
    historical_exposures: list[dict] | None = None,
    drift_zscore_threshold: float = DEFAULT_DRIFT_ZSCORE_THRESHOLD,
) -> FactorExposureResult:
    """Compute portfolio factor exposures relative to benchmark.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, factor_exposures: {value, growth, ...}, ...}.
        factor_exposures values are z-scores.
    benchmark_positions : list[dict] | None
        Same structure; used to compute active exposures.
    historical_exposures : list[dict] | None
        Past snapshots: [{date, exposures: {value: ..., ...}}, ...].
        Used to detect drift / unintended bets.
    drift_zscore_threshold : float
        Number of standard deviations from the historical mean a factor
        must move before being flagged as drift. Defaults to
        ``DEFAULT_DRIFT_ZSCORE_THRESHOLD`` (2.0).

    Returns
    -------
    FactorExposureResult
    """
    # Weighted average factor exposures for portfolio
    portfolio_exp: dict[str, float] = {f: 0.0 for f in FACTORS}
    for p in positions:
        w = p.get("weight", 0.0)
        fe = p.get("factor_exposures", {})
        for factor in FACTORS:
            portfolio_exp[factor] += w * fe.get(factor, 0.0)

    # Benchmark exposures
    benchmark_exp: dict[str, float] = {f: 0.0 for f in FACTORS}
    if benchmark_positions:
        for p in benchmark_positions:
            w = p.get("weight", 0.0)
            fe = p.get("factor_exposures", {})
            for factor in FACTORS:
                benchmark_exp[factor] += w * fe.get(factor, 0.0)

    # Active (relative) exposures
    active_exp: dict[str, float] = {
        f: portfolio_exp[f] - benchmark_exp[f] for f in FACTORS
    }

    # Factor contributions: approximate as active_exposure * factor_return_estimate
    # Without factor returns, we use exposure magnitude as proxy contribution
    factor_contributions: dict[str, float] = {
        f: active_exp[f] for f in FACTORS
    }

    # Detect unintended factor bets
    unintended_flags: list[dict] = []

    # Flag any active exposure > 0.5 in absolute value
    for factor in FACTORS:
        if abs(active_exp[factor]) > 0.5:
            unintended_flags.append({
                "factor": factor,
                "active_exposure": active_exp[factor],
                "severity": "HIGH" if abs(active_exp[factor]) > 1.0 else "MEDIUM",
                "message": (
                    f"Active {factor} exposure of {active_exp[factor]:.2f} "
                    f"exceeds threshold"
                ),
            })

    # Check for drift from historical average
    if historical_exposures and len(historical_exposures) >= 2:
        for factor in FACTORS:
            hist_vals = [
                h.get("exposures", {}).get(factor, 0.0)
                for h in historical_exposures
            ]
            if len(hist_vals) >= 2:
                hist_mean = sum(hist_vals) / len(hist_vals)
                hist_std = math.sqrt(
                    sum((v - hist_mean) ** 2 for v in hist_vals) / len(hist_vals)
                )
                current = portfolio_exp[factor]
                drift_threshold = drift_zscore_threshold * hist_std
                if hist_std > 0 and abs(current - hist_mean) > drift_threshold:
                    unintended_flags.append({
                        "factor": factor,
                        "active_exposure": current,
                        "severity": "DRIFT",
                        "message": (
                            f"{factor} exposure {current:.2f} has drifted "
                            f"from historical mean {hist_mean:.2f} "
                            f"(>{drift_threshold:.2f} threshold)"
                        ),
                    })

    return FactorExposureResult(
        portfolio_exposures=portfolio_exp,
        benchmark_exposures=benchmark_exp,
        active_exposures=active_exp,
        factor_contributions=factor_contributions,
        unintended_flags=unintended_flags,
    )


# ── Stress Testing ────────────────────────────────────────────────────


def _apply_shocks_to_positions(
    positions: list[dict],
    equity_shock: float,
    rate_shock_bps: float,
    spread_shock_bps: float,
    portfolio_nav: float,
) -> tuple[float, float, dict, list[dict]]:
    """Apply stress shocks to each position and compute PnL.

    Position-level shock logic:
    - Equities: apply equity_shock directly.
    - Bonds / fixed-income: approximate via duration * rate_shock + spread_shock.
    - Cash / other: no shock.

    Returns (total_pnl_dollar, total_pnl_pct, per_position_pnl, worst_list).
    """
    per_position: dict[str, dict] = {}
    total_pnl = 0.0

    for p in positions:
        ticker = p.get("ticker", "UNKNOWN")
        mv = p.get("market_value", 0.0)
        asset_class = p.get("asset_class", "equity").lower()
        beta = p.get("beta", 1.0)
        duration = p.get("duration", 0.0)
        spread_duration = p.get("spread_duration", 0.0)

        if asset_class in ("equity", "stock"):
            # Levered names (beta > 1) with a -50% shock can mathematically
            # produce <-100% loss. A position cannot be more than wiped out;
            # clamp at -100% to avoid implying liability.
            pnl_pct = max(-1.0, equity_shock * beta)
        elif asset_class in ("bond", "fixed_income", "fi"):
            # Bond PnL ~ -duration * delta_rate - spread_duration * delta_spread
            rate_chg = rate_shock_bps / 10000.0
            spread_chg = spread_shock_bps / 10000.0
            pnl_pct = -duration * rate_chg - spread_duration * spread_chg
        else:
            pnl_pct = 0.0

        pnl_dollar = mv * pnl_pct
        total_pnl += pnl_dollar

        per_position[ticker] = {
            "pnl_dollar": round(pnl_dollar, 2),
            "pnl_pct": round(pnl_pct, 4),
        }

    total_pnl_pct = (total_pnl / portfolio_nav) if portfolio_nav > 0 else 0.0

    # Sort for worst positions
    worst = sorted(
        [
            {"ticker": t, "pnl_dollar": d["pnl_dollar"], "pnl_pct": d["pnl_pct"]}
            for t, d in per_position.items()
        ],
        key=lambda x: x["pnl_dollar"],
    )

    return total_pnl, total_pnl_pct, per_position, worst


def run_stress_test(
    positions: list[dict],
    scenario_name: str,
    portfolio_nav: float,
    custom_params: dict | None = None,
) -> StressTestResult:
    """Run a named historical stress scenario on the portfolio.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, market_value, asset_class, beta, duration, spread_duration, ...}.
    scenario_name : str
        Key in HISTORICAL_SCENARIOS (e.g. "GFC_2008").
    portfolio_nav : float
        Total portfolio value.
    custom_params : dict | None
        Override scenario parameters.

    Returns
    -------
    StressTestResult
    """
    if scenario_name not in HISTORICAL_SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. "
            f"Available: {list(HISTORICAL_SCENARIOS.keys())}"
        )

    scenario = dict(HISTORICAL_SCENARIOS[scenario_name])
    if custom_params:
        scenario.update(custom_params)

    equity_shock = scenario["equity_shock"]
    rate_shock_bps = scenario["rate_shock_bps"]
    spread_shock_bps = scenario["spread_shock_bps"]
    recovery_months = scenario["recovery_months"]

    total_pnl, total_pnl_pct, per_position, worst = _apply_shocks_to_positions(
        positions, equity_shock, rate_shock_bps, spread_shock_bps, portfolio_nav,
    )

    # Max drawdown: for equities the equity_shock is the floor
    max_dd = min(total_pnl_pct, equity_shock)

    return StressTestResult(
        scenario_name=scenario_name,
        scenario_type="historical",
        total_pnl_dollar=round(total_pnl, 2),
        total_pnl_percent=round(total_pnl_pct, 4),
        max_drawdown_pct=round(max_dd, 4),
        recovery_time_months=recovery_months,
        per_position_pnl=per_position,
        worst_positions=worst[:5],
    )


def run_hypothetical_stress(
    positions: list[dict],
    equity_shock: float,
    rate_shock_bps: float,
    spread_shock_bps: float,
    portfolio_nav: float,
) -> StressTestResult:
    """Run a custom hypothetical stress scenario.

    Parameters
    ----------
    positions : list[dict]
        Same format as run_stress_test.
    equity_shock : float
        e.g. -0.30 for 30% equity decline.
    rate_shock_bps : float
        e.g. 200 for +200bp rate shock.
    spread_shock_bps : float
        e.g. 150 for +150bp spread widening.
    portfolio_nav : float
        Total portfolio value.

    Returns
    -------
    StressTestResult
    """
    total_pnl, total_pnl_pct, per_position, worst = _apply_shocks_to_positions(
        positions, equity_shock, rate_shock_bps, spread_shock_bps, portfolio_nav,
    )

    max_dd = min(total_pnl_pct, equity_shock)

    # Estimate recovery: proportional to shock severity
    est_recovery = max(1.0, abs(equity_shock) * 36.0)

    return StressTestResult(
        scenario_name="HYPOTHETICAL",
        scenario_type="hypothetical",
        total_pnl_dollar=round(total_pnl, 2),
        total_pnl_percent=round(total_pnl_pct, 4),
        max_drawdown_pct=round(max_dd, 4),
        recovery_time_months=round(est_recovery, 1),
        per_position_pnl=per_position,
        worst_positions=worst[:5],
    )


def get_available_scenarios() -> list[dict]:
    """Return list of all available stress scenarios with descriptions.

    Returns
    -------
    list[dict]
        [{name, label, equity_shock, rate_shock_bps, spread_shock_bps, recovery_months}]
    """
    result: list[dict] = []
    for name, params in HISTORICAL_SCENARIOS.items():
        result.append({
            "name": name,
            "label": params["label"],
            "equity_shock": params["equity_shock"],
            "rate_shock_bps": params["rate_shock_bps"],
            "spread_shock_bps": params["spread_shock_bps"],
            "recovery_months": params["recovery_months"],
        })
    return result
