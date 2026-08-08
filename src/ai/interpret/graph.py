"""The Layer 1 connection graph: curated cross-domain causal edges.

Per AI_THREE_LAYER_REBUILD_PLAN.md §3.2, the interpreter must NOT invent
connections between metrics. Two substrates back it:

1. ``calculation_lineage`` + ``analytics_results.inputs`` (machine-truth --
   the exact derivation DAG a metric was computed FROM). That's queried
   directly against the DB, not this module.
2. This module: a hand-curated map of causal links the lineage doesn't
   encode because they cross domains lineage was never built to span --
   e.g. "the Fed cuts rates" isn't an *input* to any DCF calculation
   row, but it's a real, well-understood mechanism by which macro
   conditions eventually move a DCF fair value.

Every edge here is a named, explained assertion an analyst would recognize
and could dispute -- this is domain knowledge encoded as data, not a
learned or inferred relationship, and it's deliberately small and reviewable
rather than exhaustive. Extend it deliberately (each edge is a claim someone
should be willing to defend), not automatically.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Edge:
    """One causal link: ``source`` influences ``target`` via ``mechanism``."""

    source: str
    target: str
    mechanism: str
    domain: str


# Node identifiers are lowercase snake_case CONCEPTS, not raw
# analytics_results.metric_name values (those are typically upper-snake,
# e.g. "ROE", "CURRENT_RATIO") -- see metric_to_node() below for the
# mapping between the two. A concept can have zero, one, or several
# metric_names feeding it.
EDGES: tuple[Edge, ...] = (
    # -- macro rates -> credit -> default risk -> cost of capital -> valuation --
    Edge("policy_rate", "credit_spreads",
         "policy tightening raises the risk-free rate and typically widens "
         "credit spreads as financing conditions tighten", "macro_credit"),
    Edge("credit_spreads", "default_risk",
         "wider spreads price in a higher market-implied probability of default",
         "macro_credit"),
    Edge("default_risk", "cost_of_debt",
         "higher perceived default risk raises the yield lenders demand, i.e. "
         "the issuer's cost of debt", "macro_credit"),
    Edge("cost_of_debt", "wacc",
         "cost of debt is a direct WACC input (weighted by the debt/capital ratio)",
         "valuation"),
    Edge("policy_rate", "cost_of_equity",
         "the risk-free rate is a direct input to cost of equity (CAPM)",
         "valuation"),
    Edge("cost_of_equity", "wacc",
         "cost of equity is a direct WACC input (weighted by the equity/capital ratio)",
         "valuation"),
    Edge("wacc", "dcf_value",
         "a higher discount rate lowers the present value of projected cash "
         "flows, i.e. DCF fair value", "valuation"),

    # -- DuPont: ratios -> ROE decomposition --
    Edge("gross_margin", "operating_margin",
         "gross margin flows through operating costs into operating margin",
         "dupont"),
    Edge("operating_margin", "net_margin",
         "operating margin flows through interest/tax into net margin", "dupont"),
    Edge("net_margin", "roe",
         "DuPont: net margin is one of the three multiplicative ROE drivers",
         "dupont"),
    Edge("asset_turnover", "roe",
         "DuPont: asset turnover (revenue/assets) is one of the three "
         "multiplicative ROE drivers", "dupont"),
    Edge("financial_leverage", "roe",
         "DuPont: financial leverage (assets/equity) is one of the three "
         "multiplicative ROE drivers -- amplifies ROE but also risk", "dupont"),
    Edge("financial_leverage", "default_risk",
         "higher leverage raises balance-sheet fragility and default risk",
         "credit_quality"),

    # -- ownership flows -> conviction --
    Edge("institutional_flows", "smart_money_conviction",
         "sustained net institutional buying is read as a conviction signal",
         "ownership"),
    Edge("insider_signals", "smart_money_conviction",
         "clustered open-market insider buying is read as a conviction signal",
         "ownership"),
    Edge("smart_money_conviction", "valuation_re_rating",
         "high conviction from informed holders can precede the market "
         "re-rating the stock's multiple", "ownership"),

    # -- sector cycle -> company KPIs --
    Edge("sector_cycle_position", "revenue_growth",
         "early-cycle sector positioning tends to lift company revenue growth; "
         "late-cycle tends to compress it", "sector"),
    Edge("revenue_growth", "operating_margin",
         "revenue growth affects operating leverage and thus operating margin",
         "sector"),
    Edge("revenue_growth", "roe",
         "revenue growth flows through profitability into ROE", "sector"),

    # -- country/geographic risk -> valuation --
    Edge("country_risk", "geographic_revenue_risk",
         "elevated country risk raises the discount applied to revenue earned "
         "in that geography", "geographic"),
    Edge("geographic_revenue_risk", "wacc",
         "geography-specific risk is often reflected as a premium added to "
         "the discount rate for that revenue stream", "geographic"),

    # -- ESG/governance -> cost of capital --
    Edge("esg_controversy", "governance_risk",
         "a material controversy is itself evidence of a governance/oversight gap",
         "esg"),
    Edge("governance_risk", "cost_of_equity",
         "markets typically demand a higher risk premium for weaker governance",
         "esg"),

    # -- technical/quant -> flows --
    Edge("price_momentum", "institutional_flows",
         "momentum strategies mechanically buy/sell into a trend, so momentum "
         "and flow direction are often self-reinforcing over short windows",
         "technical"),
)


def metric_to_node(metric_name: str) -> str | None:
    """Map an ``analytics_results.metric_name`` (upper-snake) to a graph
    concept node, or ``None`` if this metric isn't part of the curated graph.

    Deliberately explicit rather than a case-fold guess -- a metric with no
    entry here simply has no cross-domain connections surfaced, which is the
    honest answer when none have been curated yet.
    """
    return _METRIC_TO_NODE.get(metric_name.upper())


_METRIC_TO_NODE: dict[str, str] = {
    "ROE": "roe",
    "RETURN_ON_EQUITY": "roe",
    "GROSS_MARGIN": "gross_margin",
    "OPERATING_MARGIN": "operating_margin",
    "NET_MARGIN": "net_margin",
    "NET_PROFIT_MARGIN": "net_margin",
    "ASSET_TURNOVER": "asset_turnover",
    "FINANCIAL_LEVERAGE": "financial_leverage",
    "EQUITY_MULTIPLIER": "financial_leverage",
    "DEBT_TO_EQUITY": "financial_leverage",
    "REVENUE_GROWTH": "revenue_growth",
    "REVENUE_GROWTH_YOY": "revenue_growth",
    "WACC": "wacc",
    "COST_OF_DEBT": "cost_of_debt",
    "COST_OF_EQUITY": "cost_of_equity",
    "DCF_VALUE": "dcf_value",
    "DCF_FAIR_VALUE": "dcf_value",
    "DEFAULT_RISK_SCORE": "default_risk",
    "ALTMAN_Z_SCORE": "default_risk",
}


def nodes() -> set[str]:
    """Every node that appears in at least one edge."""
    out: set[str] = set()
    for e in EDGES:
        out.add(e.source)
        out.add(e.target)
    return out


def neighbors(node: str, *, direction: str = "downstream") -> list[Edge]:
    """Edges leaving (``downstream``, node is the cause) or entering
    (``upstream``, node is the effect) ``node``."""
    if direction not in ("downstream", "upstream"):
        raise ValueError("direction must be 'downstream' or 'upstream'")
    if direction == "downstream":
        return [e for e in EDGES if e.source == node]
    return [e for e in EDGES if e.target == node]


def find_paths(start: str, end: str, *, max_depth: int = 4) -> list[list[Edge]]:
    """All simple (no-repeated-node) paths from ``start`` to ``end``, up to
    ``max_depth`` edges, via DFS. Small graph, exhaustive search is fine.
    """
    if start == end:
        return []
    paths: list[list[Edge]] = []

    def _dfs(current: str, path: list[Edge], visited: set[str]) -> None:
        if len(path) >= max_depth:
            return
        for edge in neighbors(current, direction="downstream"):
            if edge.target in visited:
                continue
            new_path = path + [edge]
            if edge.target == end:
                paths.append(new_path)
                continue
            _dfs(edge.target, new_path, visited | {edge.target})

    _dfs(start, [], {start})
    return paths


def connected_subgraph(node_set: set[str], *, max_hops: int = 1) -> list[Edge]:
    """Every edge within ``max_hops`` of any node in ``node_set`` (either
    direction). Used to surface "the most decision-relevant links" for a
    subject's actual computed metrics, without walking the whole graph.
    """
    frontier = set(node_set)
    seen_edges: dict[tuple[str, str], Edge] = {}
    for _ in range(max_hops):
        next_frontier: set[str] = set()
        for n in frontier:
            for e in neighbors(n, direction="downstream") + neighbors(n, direction="upstream"):
                seen_edges[(e.source, e.target)] = e
                next_frontier.add(e.source)
                next_frontier.add(e.target)
        frontier = next_frontier - node_set
        if not frontier:
            break
    return list(seen_edges.values())


def describe_chain(edges: list[Edge]) -> str:
    """Render a path as a human-readable causal chain, e.g.
    ``"policy_rate -> credit_spreads (policy tightening ... ) -> ..."``.
    Empty input renders as an empty string.
    """
    if not edges:
        return ""
    parts = [edges[0].source]
    for e in edges:
        parts.append(f"--[{e.mechanism}]--> {e.target}")
    return " ".join(parts)
