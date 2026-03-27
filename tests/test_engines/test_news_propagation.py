"""Tests for the news propagation engine (Pillar 3 Phase 2 -- Part 5)."""

import pytest

from src.engines.news_propagation import (
    PropagationTarget,
    PropagationResult,
    PROPAGATION_CONFIG,
    classify_event_for_propagation,
    compute_propagation_targets,
    apply_sector_propagation,
    apply_macro_propagation,
    filter_by_preferences,
    propagate_event,
)


# ═══════════════════════════════════════════════════════════════════════════
# TestClassifyEvent
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyEvent:
    def test_bankruptcy_event(self):
        article = {"title": "Company files for Chapter 11 bankruptcy protection", "text": ""}
        result = classify_event_for_propagation(article)
        assert result is not None
        event_cat, prop_type = result
        assert event_cat == "bankruptcy"
        assert prop_type in ("SUPPLY_CHAIN", "CUSTOMER", "COMPETITIVE")

    def test_disruption_event(self):
        article = {"title": "Major supply chain disruption hits semiconductor factories", "text": "Factory closure reported."}
        result = classify_event_for_propagation(article)
        assert result is not None
        event_cat, _ = result
        assert event_cat == "disruption"

    def test_regulation_event(self):
        article = {"title": "New regulatory compliance rules announced", "text": "The regulation impacts all banks."}
        result = classify_event_for_propagation(article)
        assert result is not None
        event_cat, prop_type = result
        assert event_cat == "regulation"
        assert prop_type == "SECTOR"

    def test_non_propagatable(self):
        article = {"title": "Company holds annual picnic", "text": "The event was well attended."}
        result = classify_event_for_propagation(article)
        assert result is None

    def test_edge_empty_article(self):
        article = {"title": "", "text": ""}
        result = classify_event_for_propagation(article)
        assert result is None

    def test_multiple_signals_picks_strongest(self):
        article = {
            "title": "Bankruptcy filing amid supply disruption and shortage",
            "text": "Chapter 11 bankruptcy and supply chain disruption at factory closure",
        }
        result = classify_event_for_propagation(article)
        assert result is not None
        event_cat, _ = result
        # Both bankruptcy and disruption have signals; should pick the one with more keywords
        assert event_cat in ("bankruptcy", "disruption")


# ═══════════════════════════════════════════════════════════════════════════
# TestComputeTargets
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeTargets:
    def test_single_hop(self):
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-002", "relationship_type": "SUPPLIER", "revenue_pct": 0.5},
        ]
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", relationships, max_hops=1)
        assert len(targets) == 1
        assert targets[0].target_entity_id == "ENT-002"
        assert targets[0].hop_number == 1

    def test_two_hops(self):
        relationships = [
            {
                "source_id": "ENT-001",
                "target_id": "ENT-002",
                "relationship_type": "SUPPLIER",
                "revenue_pct": 0.5,
                "second_degree_targets": [
                    {"target_id": "ENT-003", "relationship_type": "SUPPLIER"},
                ],
            },
        ]
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", relationships, max_hops=2)
        assert len(targets) == 2
        ids = {t.target_entity_id for t in targets}
        assert "ENT-002" in ids
        assert "ENT-003" in ids
        hop2 = [t for t in targets if t.hop_number == 2]
        assert len(hop2) == 1

    def test_max_hops_one(self):
        relationships = [
            {
                "source_id": "ENT-001",
                "target_id": "ENT-002",
                "relationship_type": "SUPPLIER",
                "revenue_pct": 1.0,
                "second_degree_targets": [
                    {"target_id": "ENT-003", "relationship_type": "SUPPLIER"},
                ],
            },
        ]
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", relationships, max_hops=1)
        assert len(targets) == 1
        assert targets[0].target_entity_id == "ENT-002"

    def test_no_relationships(self):
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", [])
        assert targets == []

    def test_revenue_weighting(self):
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-002", "relationship_type": "SUPPLIER", "revenue_pct": 0.8},
            {"source_id": "ENT-001", "target_id": "ENT-003", "relationship_type": "SUPPLIER", "revenue_pct": 0.2},
        ]
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", relationships)
        t1 = next(t for t in targets if t.target_entity_id == "ENT-002")
        t2 = next(t for t in targets if t.target_entity_id == "ENT-003")
        assert t1.relevance_score > t2.relevance_score

    def test_deduplication(self):
        relationships = [
            {
                "source_id": "ENT-001",
                "target_id": "ENT-002",
                "relationship_type": "SUPPLIER",
                "revenue_pct": 0.5,
                "second_degree_targets": [
                    {"target_id": "ENT-002", "relationship_type": "SUPPLIER"},  # duplicate
                ],
            },
        ]
        targets = compute_propagation_targets("ENT-001", "bankruptcy", "SUPPLY_CHAIN", relationships)
        ids = [t.target_entity_id for t in targets]
        assert ids.count("ENT-002") == 1


# ═══════════════════════════════════════════════════════════════════════════
# TestSectorPropagation
# ═══════════════════════════════════════════════════════════════════════════


class TestSectorPropagation:
    def test_normal_sector_propagation(self):
        entities = [
            {"entity_id": "ENT-010", "entity_name": "Company A"},
            {"entity_id": "ENT-011", "entity_name": "Company B"},
        ]
        targets = apply_sector_propagation("regulation", "Industrials", entities)
        assert len(targets) == 2
        for t in targets:
            assert t.propagation_type == "SECTOR"
            assert t.hop_number == 1

    def test_empty_sector(self):
        targets = apply_sector_propagation("regulation", "Industrials", [])
        assert targets == []

    def test_multiple_entities(self):
        entities = [{"entity_id": f"ENT-{i}"} for i in range(5)]
        targets = apply_sector_propagation("commodity_price", "Materials", entities)
        assert len(targets) == 5

    def test_relevance_value(self):
        entities = [{"entity_id": "ENT-100"}]
        targets = apply_sector_propagation("regulation", "Industrials", entities)
        assert len(targets) == 1
        assert targets[0].relevance_score == 0.15


# ═══════════════════════════════════════════════════════════════════════════
# TestMacroPropagation
# ═══════════════════════════════════════════════════════════════════════════


class TestMacroPropagation:
    def test_rate_decision(self):
        sector_entities = {
            "Financials": [{"entity_id": "F1"}, {"entity_id": "F2"}],
            "Real Estate": [{"entity_id": "RE1"}],
        }
        targets = apply_macro_propagation("rate_decision", ["Financials", "Real Estate"], sector_entities)
        assert len(targets) == 3
        ids = {t.target_entity_id for t in targets}
        assert "F1" in ids and "F2" in ids and "RE1" in ids

    def test_employment_event(self):
        sector_entities = {
            "Consumer Discretionary": [{"entity_id": "CD1"}],
        }
        targets = apply_macro_propagation("employment", ["Consumer Discretionary"], sector_entities)
        assert len(targets) == 1
        assert targets[0].propagation_type == "MACRO"

    def test_no_matching_sectors(self):
        sector_entities = {"Industrials": [{"entity_id": "I1"}]}
        targets = apply_macro_propagation("rate_decision", ["Financials"], sector_entities)
        assert targets == []

    def test_multiple_sectors(self):
        sector_entities = {
            "Financials": [{"entity_id": "F1"}],
            "Utilities": [{"entity_id": "U1"}],
            "Real Estate": [{"entity_id": "RE1"}],
        }
        targets = apply_macro_propagation("rate_decision", ["Financials", "Utilities", "Real Estate"], sector_entities)
        assert len(targets) == 3


# ═══════════════════════════════════════════════════════════════════════════
# TestFilterPreferences
# ═══════════════════════════════════════════════════════════════════════════


class TestFilterPreferences:
    def test_all_enabled(self):
        targets = [
            PropagationTarget("E1", "SUPPLY_CHAIN", 1, 0.3, "HIGH", "test"),
            PropagationTarget("E2", "SECTOR", 1, 0.15, "MEDIUM", "test"),
        ]
        prefs = {"SUPPLY_CHAIN": True, "SECTOR": True}
        filtered = filter_by_preferences(targets, prefs)
        assert len(filtered) == 2

    def test_some_disabled(self):
        targets = [
            PropagationTarget("E1", "SUPPLY_CHAIN", 1, 0.3, "HIGH", "test"),
            PropagationTarget("E2", "SECTOR", 1, 0.15, "MEDIUM", "test"),
            PropagationTarget("E3", "MACRO", 1, 0.15, "MEDIUM", "test"),
        ]
        prefs = {"SUPPLY_CHAIN": True, "SECTOR": False, "MACRO": True}
        filtered = filter_by_preferences(targets, prefs)
        assert len(filtered) == 2
        ids = {t.target_entity_id for t in filtered}
        assert "E2" not in ids

    def test_empty_preferences(self):
        targets = [PropagationTarget("E1", "SUPPLY_CHAIN", 1, 0.3, "HIGH", "test")]
        filtered = filter_by_preferences(targets, {})
        assert len(filtered) == 1


# ═══════════════════════════════════════════════════════════════════════════
# TestPropagateEvent
# ═══════════════════════════════════════════════════════════════════════════


class TestPropagateEvent:
    def test_end_to_end_supply_chain(self):
        article = {"title": "Supply chain disruption at key factory closure", "text": "Shortage of parts."}
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-002", "relationship_type": "SUPPLIER", "revenue_pct": 0.5},
        ]
        result = propagate_event("ENT-001", article, relationships, {})
        assert result is not None
        assert isinstance(result, PropagationResult)
        assert result.source_entity_id == "ENT-001"
        assert result.total_affected >= 1

    def test_competitive_event(self):
        article = {"title": "New product launch and unveiling", "text": "The product release is major."}
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-005", "relationship_type": "COMPETITOR", "revenue_pct": 1.0},
        ]
        result = propagate_event("ENT-001", article, relationships, {})
        assert result is not None
        assert result.event_category == "product_launch"

    def test_macro_event(self):
        article = {"title": "Fed rate decision: FOMC raises interest rate", "text": "Rate hike announced."}
        sector_entities = {
            "Financials": [{"entity_id": "FIN1"}],
            "Real Estate": [{"entity_id": "RE1"}],
        }
        result = propagate_event("MACRO", article, [], sector_entities)
        assert result is not None
        assert result.total_affected >= 1

    def test_no_event_detected(self):
        article = {"title": "Company holds annual picnic", "text": "Good weather."}
        result = propagate_event("ENT-001", article, [], {})
        assert result is None

    def test_combined_targets(self):
        article = {"title": "Company files bankruptcy Chapter 11", "text": "Insolvency filing."}
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-002", "relationship_type": "SUPPLIER", "revenue_pct": 0.5},
            {"source_id": "ENT-001", "target_id": "ENT-003", "relationship_type": "CUSTOMER", "revenue_pct": 0.3},
        ]
        result = propagate_event("ENT-001", article, relationships, {})
        assert result is not None
        assert result.total_affected >= 1

    def test_empty_relationships_and_sectors(self):
        article = {"title": "Supply chain disruption and shortage", "text": "Factory closure."}
        result = propagate_event("ENT-001", article, [], {})
        assert result is not None
        assert result.total_affected == 0

    def test_user_filtering(self):
        article = {"title": "Supply chain disruption and shortage", "text": "Factory closure."}
        relationships = [
            {"source_id": "ENT-001", "target_id": "ENT-002", "relationship_type": "SUPPLIER", "revenue_pct": 0.5},
        ]
        prefs = {"SUPPLY_CHAIN": False}
        result = propagate_event("ENT-001", article, relationships, {}, user_preferences=prefs)
        assert result is not None
        assert result.total_affected == 0
