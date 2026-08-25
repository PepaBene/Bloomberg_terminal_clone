"""Unit tests for the Layer 1 connection graph (src/ai/interpret/graph.py).

Everything here is pure -- no DB, no LLM call.
"""
from __future__ import annotations

from src.ai.interpret.graph import (
    Edge,
    connected_subgraph,
    describe_chain,
    find_paths,
    metric_to_node,
    neighbors,
    nodes,
)


def test_nodes_includes_known_concepts():
    all_nodes = nodes()
    assert "policy_rate" in all_nodes
    assert "dcf_value" in all_nodes
    assert "roe" in all_nodes


def test_neighbors_downstream():
    edges = neighbors("policy_rate", direction="downstream")
    targets = {e.target for e in edges}
    assert "credit_spreads" in targets
    assert "cost_of_equity" in targets


def test_neighbors_upstream():
    edges = neighbors("roe", direction="upstream")
    sources = {e.source for e in edges}
    assert {"net_margin", "asset_turnover", "financial_leverage"}.issubset(sources)


def test_neighbors_invalid_direction_raises():
    import pytest
    with pytest.raises(ValueError):
        neighbors("roe", direction="sideways")


def test_neighbors_unknown_node_returns_empty():
    assert neighbors("not_a_real_node", direction="downstream") == []


def test_find_paths_known_macro_to_valuation_chain():
    paths = find_paths("policy_rate", "dcf_value", max_depth=5)
    assert len(paths) >= 1
    # every path must actually end at dcf_value and start right after policy_rate
    for path in paths:
        assert path[-1].target == "dcf_value"
        assert path[0].source == "policy_rate"


def test_find_paths_no_path_between_disconnected_concepts():
    assert find_paths("price_momentum", "esg_controversy", max_depth=2) == []


def test_find_paths_same_start_and_end_is_empty():
    assert find_paths("roe", "roe") == []


def test_find_paths_respects_max_depth():
    # dupont chain gross_margin -> operating_margin -> net_margin -> roe is 3 hops
    assert find_paths("gross_margin", "roe", max_depth=2) == []
    assert len(find_paths("gross_margin", "roe", max_depth=3)) >= 1


def test_connected_subgraph_one_hop():
    sub = connected_subgraph({"roe"}, max_hops=1)
    involved = {n for e in sub for n in (e.source, e.target)}
    assert "net_margin" in involved
    assert "financial_leverage" in involved


def test_connected_subgraph_two_hops_reaches_further():
    one_hop = connected_subgraph({"roe"}, max_hops=1)
    two_hop = connected_subgraph({"roe"}, max_hops=2)
    assert len(two_hop) >= len(one_hop)


def test_connected_subgraph_empty_input():
    assert connected_subgraph(set(), max_hops=2) == []


def test_describe_chain_empty():
    assert describe_chain([]) == ""


def test_describe_chain_renders_path():
    edges = [Edge("a", "b", "a causes b", "test"), Edge("b", "c", "b causes c", "test")]
    rendered = describe_chain(edges)
    assert rendered.startswith("a")
    assert "b" in rendered and "c" in rendered
    assert "a causes b" in rendered


def test_metric_to_node_known_mappings():
    assert metric_to_node("ROE") == "roe"
    assert metric_to_node("roe") == "roe"  # case-insensitive
    assert metric_to_node("WACC") == "wacc"


def test_metric_to_node_unknown_returns_none():
    assert metric_to_node("SOME_UNMAPPED_METRIC") is None


def test_every_edge_endpoint_is_a_nonempty_string():
    from src.ai.interpret.graph import EDGES
    for e in EDGES:
        assert e.source and e.target and e.mechanism and e.domain
        assert e.source != e.target  # no self-loops
