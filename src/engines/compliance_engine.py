"""Pillar 4 Phase 3 — Compliance Engine.

Pure computation engine for investment compliance rule evaluation,
pre-trade checks, and compliance reporting.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────────

RULE_TYPES = {"POSITION_LIMIT", "SECTOR_LIMIT", "QUALITY", "VALUATION", "RISK", "CUSTOM"}
COMPARISONS = {"LT", "GT", "LTE", "GTE", "EQ", "BETWEEN"}
SEVERITIES = {"WARNING", "BREACH"}
STATUSES = {"PASS", "WARNING", "BREACH", "N_A"}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class ComplianceCheck:
    """Result of a single compliance rule evaluation."""

    rule_name: str
    rule_type: str
    status: str  # PASS / WARNING / BREACH / N_A
    current_value: float | None
    threshold: float | None
    breach_positions: list[dict] | None
    notes: str


@dataclass
class PreTradeResult:
    """Result of a pre-trade compliance check."""

    can_proceed: bool
    warnings: list[str]
    breaches: list[str]
    checks: list[ComplianceCheck]


@dataclass
class ComplianceSummary:
    """Aggregated result of all compliance rule evaluations."""

    total_rules: int
    passed: int
    warnings: int
    breaches: int
    na: int
    results: list[ComplianceCheck]


# ── Comparison Evaluator ─────────────────────────────────────────────────


def evaluate_comparison(
    value: float,
    comparison: str,
    threshold: float,
    upper_threshold: float | None = None,
) -> bool:
    """Evaluate a generic comparison.

    Parameters
    ----------
    value : float
        The value to test.
    comparison : str
        One of LT, GT, LTE, GTE, EQ, BETWEEN.
    threshold : float
        Primary threshold (lower bound for BETWEEN).
    upper_threshold : float | None
        Upper bound, required for BETWEEN.

    Returns
    -------
    bool
        True if the comparison holds.
    """
    comparison = comparison.upper()
    if comparison == "LT":
        return value < threshold
    elif comparison == "GT":
        return value > threshold
    elif comparison == "LTE":
        return value <= threshold
    elif comparison == "GTE":
        return value >= threshold
    elif comparison == "EQ":
        return abs(value - threshold) < 1e-9
    elif comparison == "BETWEEN":
        if upper_threshold is None:
            return False
        return threshold <= value <= upper_threshold
    return False


# ── Position Limit ───────────────────────────────────────────────────────


def check_position_limit(
    positions: list[dict],
    rule: dict,
) -> ComplianceCheck:
    """Check that no single position exceeds the maximum weight.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, ...}. Weight in percentage (e.g. 10.0 = 10%).
    rule : dict
        {rule_name, max_weight, severity?, ...}.

    Returns
    -------
    ComplianceCheck
    """
    rule_name = rule.get("rule_name", "Position Limit")
    max_weight = rule.get("max_weight", 100.0)
    severity = rule.get("severity", "BREACH")

    if not positions:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="POSITION_LIMIT",
            status="N_A",
            current_value=None,
            threshold=max_weight,
            breach_positions=None,
            notes="No positions to evaluate.",
        )

    breaches: list[dict] = []
    max_found = 0.0

    for p in positions:
        w = p.get("weight", 0.0)
        if w > max_found:
            max_found = w
        if w > max_weight:
            breaches.append({"ticker": p.get("ticker", "?"), "weight": w})

    if breaches:
        status = severity if severity in SEVERITIES else "BREACH"
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="POSITION_LIMIT",
            status=status,
            current_value=max_found,
            threshold=max_weight,
            breach_positions=breaches,
            notes=f"{len(breaches)} position(s) exceed {max_weight}% limit.",
        )

    return ComplianceCheck(
        rule_name=rule_name,
        rule_type="POSITION_LIMIT",
        status="PASS",
        current_value=max_found,
        threshold=max_weight,
        breach_positions=None,
        notes=f"All positions within {max_weight}% limit.",
    )


# ── Sector Limit ─────────────────────────────────────────────────────────


def check_sector_limit(
    positions: list[dict],
    rule: dict,
) -> ComplianceCheck:
    """Check that no sector exceeds the maximum sector weight.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, sector, weight, ...}. Weight in percentage.
    rule : dict
        {rule_name, max_sector_weight, target_sector? (optional), severity?, ...}.

    Returns
    -------
    ComplianceCheck
    """
    rule_name = rule.get("rule_name", "Sector Limit")
    max_sector_weight = rule.get("max_sector_weight", 100.0)
    target_sector = rule.get("target_sector")  # None = check all sectors
    severity = rule.get("severity", "BREACH")

    if not positions:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="SECTOR_LIMIT",
            status="N_A",
            current_value=None,
            threshold=max_sector_weight,
            breach_positions=None,
            notes="No positions to evaluate.",
        )

    # Aggregate weights by sector
    sector_weights: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        sector_weights[sector] = sector_weights.get(sector, 0.0) + p.get("weight", 0.0)

    breaches: list[dict] = []
    max_sector_found = 0.0

    sectors_to_check = (
        {target_sector: sector_weights.get(target_sector, 0.0)}
        if target_sector
        else sector_weights
    )

    for sector, w in sectors_to_check.items():
        if w > max_sector_found:
            max_sector_found = w
        if w > max_sector_weight:
            breaches.append({"sector": sector, "weight": round(w, 4)})

    if breaches:
        status = severity if severity in SEVERITIES else "BREACH"
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="SECTOR_LIMIT",
            status=status,
            current_value=round(max_sector_found, 4),
            threshold=max_sector_weight,
            breach_positions=breaches,
            notes=f"{len(breaches)} sector(s) exceed {max_sector_weight}% limit.",
        )

    return ComplianceCheck(
        rule_name=rule_name,
        rule_type="SECTOR_LIMIT",
        status="PASS",
        current_value=round(max_sector_found, 4),
        threshold=max_sector_weight,
        breach_positions=None,
        notes=f"All sectors within {max_sector_weight}% limit.",
    )


# ── Quality Constraint ───────────────────────────────────────────────────


def check_quality_constraint(
    positions: list[dict],
    scores: dict,
    rule: dict,
) -> ComplianceCheck:
    """Check quality score constraints (Piotroski, Altman Z, etc.).

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, ...}.
    scores : dict
        Mapping ticker -> score value (e.g. {"AAPL": 7, "MSFT": 8}).
    rule : dict
        {rule_name, metric, comparison, threshold, upper_threshold?, severity?}.

    Returns
    -------
    ComplianceCheck
    """
    rule_name = rule.get("rule_name", "Quality Constraint")
    metric = rule.get("metric", "quality_score")
    comparison = rule.get("comparison", "GTE")
    threshold = rule.get("threshold", 0.0)
    upper_threshold = rule.get("upper_threshold")
    severity = rule.get("severity", "BREACH")

    if not positions or not scores:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="QUALITY",
            status="N_A",
            current_value=None,
            threshold=threshold,
            breach_positions=None,
            notes=f"No data for {metric} evaluation.",
        )

    breaches: list[dict] = []
    evaluated_values: list[float] = []

    for p in positions:
        ticker = p.get("ticker", "")
        if ticker in scores:
            score = scores[ticker]
            evaluated_values.append(score)
            if not evaluate_comparison(score, comparison, threshold, upper_threshold):
                breaches.append({
                    "ticker": ticker,
                    metric: score,
                    "weight": p.get("weight", 0.0),
                })

    if not evaluated_values:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="QUALITY",
            status="N_A",
            current_value=None,
            threshold=threshold,
            breach_positions=None,
            notes=f"No {metric} scores matched any position.",
        )

    avg_value = sum(evaluated_values) / len(evaluated_values)

    if breaches:
        status = severity if severity in SEVERITIES else "BREACH"
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="QUALITY",
            status=status,
            current_value=round(avg_value, 4),
            threshold=threshold,
            breach_positions=breaches,
            notes=f"{len(breaches)} position(s) fail {metric} {comparison} {threshold}.",
        )

    return ComplianceCheck(
        rule_name=rule_name,
        rule_type="QUALITY",
        status="PASS",
        current_value=round(avg_value, 4),
        threshold=threshold,
        breach_positions=None,
        notes=f"All positions satisfy {metric} {comparison} {threshold}.",
    )


# ── Valuation Constraint ─────────────────────────────────────────────────


def check_valuation_constraint(
    positions: list[dict],
    valuations: dict,
    rule: dict,
) -> ComplianceCheck:
    """Check valuation constraints (P/E, P/B ranges, etc.).

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, ...}.
    valuations : dict
        Mapping ticker -> valuation value (e.g. {"AAPL": 25.3, "MSFT": 30.1}).
    rule : dict
        {rule_name, metric, comparison, threshold, upper_threshold?, severity?}.

    Returns
    -------
    ComplianceCheck
    """
    rule_name = rule.get("rule_name", "Valuation Constraint")
    metric = rule.get("metric", "pe_ratio")
    comparison = rule.get("comparison", "LTE")
    threshold = rule.get("threshold", 0.0)
    upper_threshold = rule.get("upper_threshold")
    severity = rule.get("severity", "BREACH")

    if not positions or not valuations:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="VALUATION",
            status="N_A",
            current_value=None,
            threshold=threshold,
            breach_positions=None,
            notes=f"No data for {metric} evaluation.",
        )

    breaches: list[dict] = []
    evaluated_values: list[float] = []

    for p in positions:
        ticker = p.get("ticker", "")
        if ticker in valuations:
            val = valuations[ticker]
            evaluated_values.append(val)
            if not evaluate_comparison(val, comparison, threshold, upper_threshold):
                breaches.append({
                    "ticker": ticker,
                    metric: val,
                    "weight": p.get("weight", 0.0),
                })

    if not evaluated_values:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="VALUATION",
            status="N_A",
            current_value=None,
            threshold=threshold,
            breach_positions=None,
            notes=f"No {metric} values matched any position.",
        )

    avg_value = sum(evaluated_values) / len(evaluated_values)

    if breaches:
        status = severity if severity in SEVERITIES else "BREACH"
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="VALUATION",
            status=status,
            current_value=round(avg_value, 4),
            threshold=threshold,
            breach_positions=breaches,
            notes=f"{len(breaches)} position(s) fail {metric} {comparison} {threshold}.",
        )

    return ComplianceCheck(
        rule_name=rule_name,
        rule_type="VALUATION",
        status="PASS",
        current_value=round(avg_value, 4),
        threshold=threshold,
        breach_positions=None,
        notes=f"All positions satisfy {metric} {comparison} {threshold}.",
    )


# ── Risk Constraint ──────────────────────────────────────────────────────


def check_risk_constraint(
    risk_data: dict,
    rule: dict,
) -> ComplianceCheck:
    """Check risk constraints (VaR limits, beta limits, etc.).

    Parameters
    ----------
    risk_data : dict
        E.g. {var_95: 0.02, beta: 1.1, volatility: 0.15, ...}.
    rule : dict
        {rule_name, metric, comparison, threshold, upper_threshold?, severity?}.

    Returns
    -------
    ComplianceCheck
    """
    rule_name = rule.get("rule_name", "Risk Constraint")
    metric = rule.get("metric", "var_95")
    comparison = rule.get("comparison", "LTE")
    threshold = rule.get("threshold", 0.0)
    upper_threshold = rule.get("upper_threshold")
    severity = rule.get("severity", "BREACH")

    if not risk_data or metric not in risk_data:
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="RISK",
            status="N_A",
            current_value=None,
            threshold=threshold,
            breach_positions=None,
            notes=f"No data for {metric}.",
        )

    value = risk_data[metric]

    if evaluate_comparison(value, comparison, threshold, upper_threshold):
        return ComplianceCheck(
            rule_name=rule_name,
            rule_type="RISK",
            status="PASS",
            current_value=round(value, 6),
            threshold=threshold,
            breach_positions=None,
            notes=f"{metric} = {value:.6f} satisfies {comparison} {threshold}.",
        )

    status = severity if severity in SEVERITIES else "BREACH"
    return ComplianceCheck(
        rule_name=rule_name,
        rule_type="RISK",
        status=status,
        current_value=round(value, 6),
        threshold=threshold,
        breach_positions=None,
        notes=f"{metric} = {value:.6f} violates {comparison} {threshold}.",
    )


# ── Simulate Trade ───────────────────────────────────────────────────────


def simulate_trade(
    positions: list[dict],
    trade: dict,
) -> list[dict]:
    """Apply a proposed trade to a position list and return new positions.

    Parameters
    ----------
    positions : list[dict]
        Each: {ticker, weight, market_value, sector?, ...}.
    trade : dict
        {ticker, action (BUY/SELL), weight_delta, sector?, ...}.
        weight_delta is the absolute weight change in percentage points.

    Returns
    -------
    list[dict]
        New positions list after the trade is applied.
    """
    ticker = trade.get("ticker", "")
    action = trade.get("action", "BUY").upper()
    weight_delta = trade.get("weight_delta", 0.0)
    sector = trade.get("sector", "Unknown")

    # Deep copy
    new_positions = [dict(p) for p in positions]

    found = False
    for p in new_positions:
        if p.get("ticker") == ticker:
            found = True
            if action == "BUY":
                p["weight"] = p.get("weight", 0.0) + weight_delta
            elif action == "SELL":
                p["weight"] = max(0.0, p.get("weight", 0.0) - weight_delta)
            break

    if not found and action == "BUY":
        new_positions.append({
            "ticker": ticker,
            "weight": weight_delta,
            "sector": sector,
        })

    # Remove positions with zero weight
    new_positions = [p for p in new_positions if p.get("weight", 0.0) > 0.0]

    return new_positions


# ── Evaluate All Rules ───────────────────────────────────────────────────


def evaluate_all_rules(
    positions: list[dict],
    rules: list[dict],
    context: dict,
) -> ComplianceSummary:
    """Batch-evaluate all compliance rules.

    Parameters
    ----------
    positions : list[dict]
        Portfolio positions.
    rules : list[dict]
        Each rule has a 'rule_type' key plus type-specific fields.
    context : dict
        Additional data: {scores?, valuations?, risk_data?}.

    Returns
    -------
    ComplianceSummary
    """
    results: list[ComplianceCheck] = []

    for rule in rules:
        rule_type = rule.get("rule_type", "CUSTOM")

        if rule_type == "POSITION_LIMIT":
            results.append(check_position_limit(positions, rule))
        elif rule_type == "SECTOR_LIMIT":
            results.append(check_sector_limit(positions, rule))
        elif rule_type == "QUALITY":
            scores = context.get("scores", {})
            results.append(check_quality_constraint(positions, scores, rule))
        elif rule_type == "VALUATION":
            valuations = context.get("valuations", {})
            results.append(check_valuation_constraint(positions, valuations, rule))
        elif rule_type == "RISK":
            risk_data = context.get("risk_data", {})
            results.append(check_risk_constraint(risk_data, rule))
        else:
            results.append(ComplianceCheck(
                rule_name=rule.get("rule_name", "Unknown Rule"),
                rule_type=rule_type,
                status="N_A",
                current_value=None,
                threshold=None,
                breach_positions=None,
                notes=f"Unsupported rule type: {rule_type}.",
            ))

    passed = sum(1 for r in results if r.status == "PASS")
    warnings = sum(1 for r in results if r.status == "WARNING")
    breaches = sum(1 for r in results if r.status == "BREACH")
    na = sum(1 for r in results if r.status == "N_A")

    return ComplianceSummary(
        total_rules=len(results),
        passed=passed,
        warnings=warnings,
        breaches=breaches,
        na=na,
        results=results,
    )


# ── Pre-Trade Check ──────────────────────────────────────────────────────


def pre_trade_check(
    current_positions: list[dict],
    proposed_trade: dict,
    rules: list[dict],
    context: dict,
) -> PreTradeResult:
    """Simulate a trade and check compliance on the resulting portfolio.

    Parameters
    ----------
    current_positions : list[dict]
        Current portfolio positions.
    proposed_trade : dict
        Trade to simulate.
    rules : list[dict]
        Compliance rules to evaluate.
    context : dict
        Additional data for rule evaluation.

    Returns
    -------
    PreTradeResult
    """
    new_positions = simulate_trade(current_positions, proposed_trade)
    summary = evaluate_all_rules(new_positions, rules, context)

    warnings_list: list[str] = []
    breaches_list: list[str] = []

    for r in summary.results:
        if r.status == "WARNING":
            warnings_list.append(f"{r.rule_name}: {r.notes}")
        elif r.status == "BREACH":
            breaches_list.append(f"{r.rule_name}: {r.notes}")

    can_proceed = len(breaches_list) == 0

    return PreTradeResult(
        can_proceed=can_proceed,
        warnings=warnings_list,
        breaches=breaches_list,
        checks=summary.results,
    )


# ── Compliance Report ────────────────────────────────────────────────────


def generate_compliance_report(summary: ComplianceSummary) -> str:
    """Generate a human-readable text compliance report.

    Parameters
    ----------
    summary : ComplianceSummary
        Result of evaluate_all_rules.

    Returns
    -------
    str
        Formatted text report.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("COMPLIANCE REPORT")
    lines.append("=" * 60)
    lines.append(f"Total Rules: {summary.total_rules}")
    lines.append(f"  Passed:   {summary.passed}")
    lines.append(f"  Warnings: {summary.warnings}")
    lines.append(f"  Breaches: {summary.breaches}")
    lines.append(f"  N/A:      {summary.na}")
    lines.append("-" * 60)

    for r in summary.results:
        lines.append(f"[{r.status}] {r.rule_name} ({r.rule_type})")
        if r.current_value is not None:
            lines.append(f"  Value: {r.current_value}  |  Threshold: {r.threshold}")
        lines.append(f"  {r.notes}")
        if r.breach_positions:
            for bp in r.breach_positions:
                lines.append(f"    -> {bp}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
