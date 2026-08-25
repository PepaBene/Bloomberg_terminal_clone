"""Tests for evals/schema.py — golden example loading."""
from __future__ import annotations

from evals.schema import GoldenExample, list_categories, load_golden_examples

EXPECTED_CATEGORIES = {
    "analyst_qa", "morning_briefing", "company_primer",
    "investment_thesis", "anomaly_narrative", "semantic_search",
}


def test_list_categories_matches_plan_layout():
    assert set(list_categories()) == EXPECTED_CATEGORIES


def test_every_category_has_at_least_two_seed_examples():
    for category in EXPECTED_CATEGORIES:
        examples = load_golden_examples(category)
        assert len(examples) >= 2, f"{category} has too few seed examples"
        for ex in examples:
            assert isinstance(ex, GoldenExample)
            assert ex.category == category
            assert ex.inputs.get("question")


def test_load_golden_examples_unknown_category_returns_empty():
    assert load_golden_examples("does_not_exist") == []


def test_analyst_qa_examples_sorted_by_id():
    examples = load_golden_examples("analyst_qa")
    ids = [e.id for e in examples]
    assert ids == sorted(ids)


def test_golden_example_defaults():
    ex = GoldenExample(id="x", category="analyst_qa", inputs={"question": "q"})
    assert ex.type == "factual"
    assert ex.must_include == []
    assert ex.must_not_include == []
    assert ex.max_tokens is None
    assert ex.expected_citations == []
