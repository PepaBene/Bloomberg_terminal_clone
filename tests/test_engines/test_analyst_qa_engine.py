"""Tests for Pillar 3 Phase 4B — Analyst Q&A Engine."""

import pytest

from src.engines.analyst_qa_engine import (
    Benchmark,
    DataSource,
    FinancialMetric,
    FollowUpSuggestion,
    QAResult,
    QuestionParsed,
    assess_data_completeness,
    assemble_qa_prompt,
    classify_question_type,
    compute_benchmarks,
    compute_confidence,
    extract_financial_metrics,
    generate_follow_ups,
    identify_required_data,
    parse_question,
    process_question,
)


# ── parse_question ────────────────────────────────────────────────────


class TestParseQuestion:
    """Tests for parse_question."""

    def test_empty_question(self):
        parsed = parse_question("")
        assert parsed.question_type == "factual"

    def test_extracts_ticker(self):
        parsed = parse_question("What is $AAPL revenue growth?")
        assert parsed.target_entity == "AAPL"

    def test_extracts_company_name_with_inc(self):
        parsed = parse_question("How is Apple Inc performing?")
        assert parsed.target_entity == "Apple Inc"

    def test_extracts_quoted_name(self):
        parsed = parse_question('What is the outlook for "Tesla Motors"?')
        assert parsed.target_entity == "Tesla Motors"

    def test_identifies_sector(self):
        parsed = parse_question("How is the technology sector performing?")
        assert parsed.target_sector == "Technology"

    def test_identifies_healthcare_sector(self):
        parsed = parse_question("What are the healthcare trends?")
        assert parsed.target_sector == "Health Care"

    def test_near_term_horizon(self):
        parsed = parse_question("What will happen next quarter?")
        assert parsed.time_horizon == "near_term"

    def test_medium_term_horizon(self):
        parsed = parse_question("What is the 12 month outlook?")
        assert parsed.time_horizon == "medium_term"

    def test_long_term_horizon(self):
        parsed = parse_question("What is the long term structural trend?")
        assert parsed.time_horizon == "long_term"

    def test_context_clues_comparison(self):
        parsed = parse_question("Compare $AAPL vs $MSFT revenue growth")
        assert "comparison_requested" in parsed.context_clues

    def test_context_clues_risk(self):
        parsed = parse_question("What are the key risks for $AAPL?")
        assert "risk_focus" in parsed.context_clues

    def test_context_clues_valuation(self):
        parsed = parse_question("What is the price target for $GOOG?")
        assert "valuation_focus" in parsed.context_clues

    def test_context_clues_explanation(self):
        parsed = parse_question("Why did $TSLA earnings miss?")
        assert "explanation_requested" in parsed.context_clues


# ── classify_question_type ────────────────────────────────────────────


class TestClassifyQuestionType:
    """Tests for classify_question_type."""

    def test_factual_question(self):
        assert classify_question_type("What is Apple's revenue?") == "factual"

    def test_comparative_question(self):
        assert classify_question_type("Compare AAPL vs MSFT") == "comparative"

    def test_forward_looking_question(self):
        assert classify_question_type("What will revenue be next year?") == "forward_looking"

    def test_scenario_question(self):
        assert classify_question_type("What if interest rates rise 200bps?") == "scenario"

    def test_thematic_question(self):
        assert classify_question_type("What are the major sector trends?") == "thematic"

    def test_synthesis_question(self):
        assert classify_question_type("Give me an overview of Tesla") == "synthesis"

    def test_relative_to_is_comparative(self):
        assert classify_question_type("How does AAPL perform relative to peers?") == "comparative"

    def test_forecast_is_forward_looking(self):
        assert classify_question_type("What is the earnings forecast?") == "forward_looking"

    def test_assuming_is_scenario(self):
        assert classify_question_type("Assuming a recession, what happens?") == "scenario"


# ── identify_required_data ────────────────────────────────────────────


class TestIdentifyRequiredData:
    """Tests for identify_required_data."""

    def test_factual_with_entity(self):
        parsed = QuestionParsed(question_type="factual", target_entity="AAPL")
        required = identify_required_data(parsed)
        assert "fundamentals" in required
        assert "filings" in required

    def test_comparative_needs_peers(self):
        parsed = QuestionParsed(question_type="comparative")
        required = identify_required_data(parsed)
        assert "peer_data" in required

    def test_forward_looking_needs_consensus(self):
        parsed = QuestionParsed(question_type="forward_looking")
        required = identify_required_data(parsed)
        assert "consensus" in required

    def test_scenario_needs_risk_factors(self):
        parsed = QuestionParsed(question_type="scenario")
        required = identify_required_data(parsed)
        assert "risk_factors" in required

    def test_risk_context_adds_risk_factors(self):
        parsed = QuestionParsed(question_type="factual", context_clues=["risk_focus"])
        required = identify_required_data(parsed)
        assert "risk_factors" in required

    def test_valuation_context_adds_consensus(self):
        parsed = QuestionParsed(question_type="factual", context_clues=["valuation_focus"])
        required = identify_required_data(parsed)
        assert "consensus" in required


# ── assemble_qa_prompt ────────────────────────────────────────────────


class TestAssembleQAPrompt:
    """Tests for assemble_qa_prompt."""

    def test_basic_prompt(self):
        parsed = QuestionParsed(question_type="factual", target_entity="AAPL")
        data_context = {"fundamentals": {"revenue": 400000}}
        prompt = assemble_qa_prompt("What is AAPL revenue?", parsed, data_context)
        assert "system_message" in prompt
        assert "user_message" in prompt
        assert "AAPL" in prompt["user_message"]

    def test_empty_context(self):
        parsed = QuestionParsed(question_type="factual")
        prompt = assemble_qa_prompt("question", parsed, {})
        assert "No data available" in prompt["context_summary"]


# ── extract_financial_metrics ─────────────────────────────────────────


class TestExtractFinancialMetrics:
    """Tests for extract_financial_metrics."""

    def test_extracts_from_fundamentals(self):
        data = {"fundamentals": {"revenue": 400000, "eps": 6.5, "revenue_growth": 8.0,
                                  "date": "2024-12-31", "source": "bloomberg"}}
        metrics = extract_financial_metrics(data, "factual")
        assert len(metrics) >= 1
        metric_names = [m.metric for m in metrics]
        assert any("Revenue" in n or "EPS" in n for n in metric_names)

    def test_no_fundamentals(self):
        metrics = extract_financial_metrics({}, "factual")
        assert metrics == []

    def test_comparative_priorities(self):
        data = {"fundamentals": {"revenue_growth": 8.0, "ebitda_margin": 35.0,
                                  "roe": 40.0, "pe_ratio": 28.0, "date": "2024"}}
        metrics = extract_financial_metrics(data, "comparative")
        metric_names = [m.metric for m in metrics]
        assert "Revenue Growth" in metric_names

    def test_forward_looking_priorities(self):
        data = {"fundamentals": {"revenue_growth": 8.0, "eps": 6.5, "ebitda": 130000,
                                  "fcf": 100000, "date": "2024"}}
        metrics = extract_financial_metrics(data, "forward_looking")
        assert len(metrics) >= 1


# ── compute_benchmarks ────────────────────────────────────────────────


class TestComputeBenchmarks:
    """Tests for compute_benchmarks."""

    def test_basic_benchmark(self):
        entity = {"revenue_growth": 15.0, "roe": 30.0}
        peers = [
            {"revenue_growth": 8.0, "roe": 15.0},
            {"revenue_growth": 10.0, "roe": 20.0},
            {"revenue_growth": 12.0, "roe": 25.0},
            {"revenue_growth": 5.0, "roe": 10.0},
        ]
        benchmarks = compute_benchmarks(entity, peers, ["revenue_growth", "roe"])
        assert len(benchmarks) == 2
        # AAPL at 15% should be top quartile
        rev_benchmark = [b for b in benchmarks if b.benchmark == "revenue_growth"][0]
        assert rev_benchmark.percentile >= 75

    def test_empty_peers(self):
        benchmarks = compute_benchmarks({"revenue_growth": 10.0}, [], ["revenue_growth"])
        assert benchmarks == []

    def test_missing_metric(self):
        entity = {"revenue_growth": 10.0}
        peers = [{"revenue_growth": 8.0}]
        benchmarks = compute_benchmarks(entity, peers, ["nonexistent"])
        assert benchmarks == []

    def test_bottom_quartile(self):
        entity = {"roe": 5.0}
        peers = [{"roe": 15.0}, {"roe": 20.0}, {"roe": 25.0}, {"roe": 30.0}]
        benchmarks = compute_benchmarks(entity, peers, ["roe"])
        assert benchmarks[0].percentile < 25
        assert "Bottom quartile" in benchmarks[0].interpretation


# ── compute_confidence ────────────────────────────────────────────────


class TestComputeConfidence:
    """Tests for compute_confidence."""

    def test_all_data_available(self):
        completeness = {"fundamentals": True, "filings": True, "transcripts": True}
        confidence, narrative = compute_confidence(completeness, "factual")
        assert confidence >= 0.8
        assert "High confidence" in narrative

    def test_no_data_available(self):
        completeness = {"fundamentals": False, "filings": False, "transcripts": False}
        confidence, narrative = compute_confidence(completeness, "factual")
        assert confidence < 0.5

    def test_empty_completeness(self):
        confidence, narrative = compute_confidence({}, "factual")
        assert confidence == 0.3
        assert "Low confidence" in narrative

    def test_scenario_gets_penalty(self):
        completeness = {"fundamentals": True, "risk_factors": True}
        conf_factual, _ = compute_confidence(completeness, "factual")
        conf_scenario, _ = compute_confidence(completeness, "scenario")
        assert conf_scenario < conf_factual

    def test_confidence_clamped(self):
        completeness = {f"src_{i}": True for i in range(20)}
        confidence, _ = compute_confidence(completeness, "factual")
        assert confidence <= 0.99


# ── generate_follow_ups ───────────────────────────────────────────────


class TestGenerateFollowUps:
    """Tests for generate_follow_ups."""

    def test_factual_follow_ups(self):
        parsed = QuestionParsed(question_type="factual", target_entity="AAPL")
        follow_ups = generate_follow_ups("What is AAPL revenue?", parsed, {})
        assert len(follow_ups) >= 1
        assert all(isinstance(f, FollowUpSuggestion) for f in follow_ups)

    def test_comparative_follow_ups(self):
        parsed = QuestionParsed(question_type="comparative", target_entity="MSFT")
        follow_ups = generate_follow_ups("How does MSFT compare?", parsed, {})
        assert any("valuation gap" in f.question.lower() or "peer" in f.question.lower()
                    for f in follow_ups)

    def test_data_gap_follow_ups(self):
        parsed = QuestionParsed(question_type="factual", target_entity="GOOG")
        context = {"data_gaps": ["consensus estimates"]}
        follow_ups = generate_follow_ups("question", parsed, context)
        assert any("consensus" in f.question.lower() for f in follow_ups)

    def test_max_five_follow_ups(self):
        parsed = QuestionParsed(question_type="synthesis", target_entity="TEST")
        context = {"data_gaps": ["gap1", "gap2", "gap3", "gap4"]}
        follow_ups = generate_follow_ups("q", parsed, context)
        assert len(follow_ups) <= 5

    def test_sorted_by_relevance(self):
        parsed = QuestionParsed(question_type="factual", target_entity="X")
        follow_ups = generate_follow_ups("q", parsed, {})
        if len(follow_ups) >= 2:
            assert follow_ups[0].relevance_score >= follow_ups[1].relevance_score


# ── assess_data_completeness ──────────────────────────────────────────


class TestAssessDataCompleteness:
    """Tests for assess_data_completeness."""

    def test_all_available(self):
        required = ["fundamentals", "filings"]
        available = {"fundamentals": {"revenue": 100}, "filings": {"risk_factors": []}}
        result = assess_data_completeness(required, available)
        assert result["overall_completeness"] == 1.0
        assert result["missing"] == []

    def test_partial_availability(self):
        required = ["fundamentals", "filings", "transcripts"]
        available = {"fundamentals": {"revenue": 100}}
        result = assess_data_completeness(required, available)
        assert abs(result["overall_completeness"] - 0.33) < 0.1
        assert "filings" in result["missing"]
        assert "transcripts" in result["missing"]

    def test_empty_required(self):
        result = assess_data_completeness([], {})
        assert result["overall_completeness"] == 1.0

    def test_gaps_identified(self):
        required = ["fundamentals", "consensus"]
        available = {"fundamentals": {"revenue": 100}}
        result = assess_data_completeness(required, available)
        assert len(result["gaps"]) >= 1
        assert any("consensus" in g.lower() for g in result["gaps"])

    def test_empty_data_not_counted(self):
        required = ["fundamentals"]
        available = {"fundamentals": {}}
        result = assess_data_completeness(required, available)
        assert result["overall_completeness"] == 0.0


# ── process_question ──────────────────────────────────────────────────


class TestProcessQuestion:
    """Tests for process_question."""

    @pytest.fixture
    def sample_entity_data(self):
        return {
            "fundamentals": {
                "revenue": 400000, "revenue_growth": 8.5, "eps": 6.5,
                "ebitda": 130000, "ebitda_margin": 35.0, "roe": 40.0,
                "roic": 25.0, "date": "2024-12-31", "source": "bloomberg",
            },
            "filings": {"risk_factors": ["Competition", "Regulation"]},
            "transcripts": [{"themes": ["AI adoption"]}],
            "consensus": {"target_price": 220.0},
        }

    @pytest.fixture
    def sample_peer_data(self):
        return [
            {"revenue_growth": 10.0, "roe": 20.0},
            {"revenue_growth": 6.0, "roe": 15.0},
            {"revenue_growth": 12.0, "roe": 25.0},
        ]

    def test_basic_question_processing(self, sample_entity_data):
        result = process_question(
            "What is $AAPL revenue growth?",
            sample_entity_data, None, None,
        )
        assert isinstance(result, QAResult)
        assert result.answer_type == "factual"
        assert result.confidence > 0
        assert len(result.confidence_narrative) > 0

    def test_with_peer_data(self, sample_entity_data, sample_peer_data):
        result = process_question(
            "Compare $AAPL vs peers",
            sample_entity_data, sample_peer_data, None,
        )
        assert result.answer_type == "comparative"

    def test_with_research_data(self, sample_entity_data):
        research = [{"id": "r1", "type": "research", "title": "AAPL Deep Dive",
                      "date": "2024-12-01", "relevance": "high", "summary": "Strong buy"}]
        result = process_question(
            "Tell me about $AAPL",
            sample_entity_data, None, research,
        )
        assert len(result.sources) >= 2  # fundamentals + research

    def test_no_data_low_confidence(self):
        result = process_question("What about $XYZ?", None, None, None)
        assert result.confidence < 0.5

    def test_follow_ups_generated(self, sample_entity_data):
        result = process_question("What is $AAPL outlook?", sample_entity_data, None, None)
        assert len(result.follow_ups) >= 1

    def test_metrics_extracted(self, sample_entity_data):
        result = process_question("What is $AAPL revenue?", sample_entity_data, None, None)
        assert len(result.metrics) >= 1

    def test_data_completeness_tracked(self, sample_entity_data):
        result = process_question("What is $AAPL revenue?", sample_entity_data, None, None)
        assert "overall_completeness" in result.data_completeness

    def test_scenario_question(self, sample_entity_data):
        result = process_question(
            "What if $AAPL revenue drops 20%?",
            sample_entity_data, None, None,
        )
        assert result.answer_type == "scenario"
