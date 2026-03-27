"""Tests for Pillar 3 Phase 4B — Semantic Search Engine."""

import math

import pytest

from src.engines.semantic_search_engine import (
    DocumentChunk,
    SearchResult,
    SearchSynthesis,
    SemanticSearchResult,
    assemble_search_prompt,
    build_search_response,
    chunk_document,
    compute_cosine_similarity,
    extract_document_metadata,
    extract_entity_mentions,
    filter_by_date_range,
    filter_by_document_type,
    rank_results,
    rerank_by_recency,
)


# ── chunk_document ────────────────────────────────────────────────────


class TestChunkDocument:
    """Tests for chunk_document."""

    def test_empty_text_returns_empty(self):
        assert chunk_document("") == []

    def test_whitespace_only_returns_empty(self):
        assert chunk_document("   \n\n   ") == []

    def test_single_short_paragraph(self):
        text = "This is a short paragraph."
        chunks = chunk_document(text, max_tokens=100)
        assert len(chunks) == 1
        assert "short paragraph" in chunks[0]

    def test_multiple_paragraphs_within_limit(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_document(text, max_tokens=100)
        assert len(chunks) == 1
        assert "First" in chunks[0]
        assert "Third" in chunks[0]

    def test_paragraphs_exceeding_limit_split(self):
        p1 = " ".join(["word"] * 50)
        p2 = " ".join(["another"] * 50)
        p3 = " ".join(["third"] * 50)
        text = f"{p1}\n\n{p2}\n\n{p3}"
        chunks = chunk_document(text, max_tokens=60, overlap_tokens=10)
        assert len(chunks) >= 2

    def test_overlap_tokens_preserved(self):
        p1 = " ".join(["alpha"] * 30)
        p2 = " ".join(["beta"] * 30)
        text = f"{p1}\n\n{p2}"
        chunks = chunk_document(text, max_tokens=35, overlap_tokens=5)
        assert len(chunks) >= 2
        # Overlap means last words of chunk 1 appear at start of chunk 2
        if len(chunks) >= 2:
            last_words = chunks[0].split()[-5:]
            first_words = chunks[1].split()[:5]
            assert last_words == first_words

    def test_no_overlap(self):
        p1 = " ".join(["alpha"] * 30)
        p2 = " ".join(["beta"] * 30)
        text = f"{p1}\n\n{p2}"
        chunks = chunk_document(text, max_tokens=35, overlap_tokens=0)
        assert len(chunks) >= 2

    def test_default_parameters(self):
        text = "A simple document.\n\nWith two paragraphs."
        chunks = chunk_document(text)
        assert len(chunks) >= 1


# ── extract_document_metadata ─────────────────────────────────────────


class TestExtractDocumentMetadata:
    """Tests for extract_document_metadata."""

    def test_empty_text(self):
        result = extract_document_metadata("", "Title")
        assert result["tickers"] == []
        assert result["word_count"] == 0

    def test_extracts_tickers(self):
        text = "$AAPL reported strong earnings. $MSFT also did well."
        result = extract_document_metadata(text, "Earnings")
        assert "AAPL" in result["tickers"]
        assert "MSFT" in result["tickers"]

    def test_extracts_financial_metrics(self):
        text = "Revenue growth was strong. EBITDA margins expanded. EPS beat estimates."
        result = extract_document_metadata(text, "Report")
        assert "revenue" in result["financial_metrics"]
        assert "ebitda" in result["financial_metrics"]
        assert "eps" in result["financial_metrics"]

    def test_extracts_dates(self):
        text = "In Q3 2024, the company reported results for 2023."
        result = extract_document_metadata(text, "Filing")
        assert any("2024" in d for d in result["dates"])
        assert any("2023" in d for d in result["dates"])

    def test_word_count(self):
        text = "one two three four five"
        result = extract_document_metadata(text, "Doc")
        assert result["word_count"] == 5


# ── compute_cosine_similarity ─────────────────────────────────────────


class TestCosineSimilarity:
    """Tests for compute_cosine_similarity."""

    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        sim = compute_cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = compute_cosine_similarity(a, b)
        assert abs(sim) < 1e-9

    def test_opposite_vectors(self):
        a = [1.0, 2.0]
        b = [-1.0, -2.0]
        sim = compute_cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-9

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert compute_cosine_similarity(a, b) == 0.0

    def test_different_lengths(self):
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        assert compute_cosine_similarity(a, b) == 0.0

    def test_empty_vectors(self):
        assert compute_cosine_similarity([], []) == 0.0

    def test_known_similarity(self):
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        expected = 1.0 / math.sqrt(2)
        sim = compute_cosine_similarity(a, b)
        assert abs(sim - expected) < 1e-6


# ── rank_results ──────────────────────────────────────────────────────


class TestRankResults:
    """Tests for rank_results."""

    def test_basic_ranking(self):
        query = [1.0, 0.0, 0.0]
        docs = [
            ("doc1", [0.0, 1.0, 0.0]),  # orthogonal
            ("doc2", [1.0, 0.0, 0.0]),  # identical
            ("doc3", [0.5, 0.5, 0.0]),  # partial match
        ]
        ranked = rank_results(query, docs, top_k=3)
        assert ranked[0][0] == "doc2"
        assert ranked[0][1] > ranked[1][1]

    def test_top_k_limits(self):
        query = [1.0, 0.0]
        docs = [("d1", [1.0, 0.0]), ("d2", [0.5, 0.5]), ("d3", [0.0, 1.0])]
        ranked = rank_results(query, docs, top_k=2)
        assert len(ranked) == 2

    def test_empty_docs(self):
        ranked = rank_results([1.0], [])
        assert ranked == []


# ── rerank_by_recency ─────────────────────────────────────────────────


class TestRerankByRecency:
    """Tests for rerank_by_recency."""

    def test_empty_results(self):
        assert rerank_by_recency([]) == []

    def test_adds_adjusted_score(self):
        results = [{"relevance_score": 0.8, "date": "2025-01-01"}]
        reranked = rerank_by_recency(results, recency_weight=0.1)
        assert "adjusted_score" in reranked[0]

    def test_newer_docs_boosted(self):
        results = [
            {"relevance_score": 0.8, "date": "2020-01-01", "id": "old"},
            {"relevance_score": 0.8, "date": "2025-12-01", "id": "new"},
        ]
        reranked = rerank_by_recency(results, recency_weight=0.3)
        assert reranked[0]["id"] == "new"

    def test_no_date_no_crash(self):
        results = [{"relevance_score": 0.8, "date": None}]
        reranked = rerank_by_recency(results)
        assert len(reranked) == 1


# ── filter_by_document_type ───────────────────────────────────────────


class TestFilterByDocumentType:
    """Tests for filter_by_document_type."""

    def test_none_allowed_returns_all(self):
        results = [{"source_type": "filing"}, {"source_type": "news"}]
        assert len(filter_by_document_type(results, None)) == 2

    def test_empty_allowed_returns_all(self):
        results = [{"source_type": "filing"}]
        assert len(filter_by_document_type(results, [])) == 1

    def test_filters_correctly(self):
        results = [
            {"source_type": "filing"},
            {"source_type": "news"},
            {"source_type": "research"},
        ]
        filtered = filter_by_document_type(results, ["filing", "research"])
        assert len(filtered) == 2

    def test_case_insensitive(self):
        results = [{"source_type": "FILING"}]
        filtered = filter_by_document_type(results, ["filing"])
        assert len(filtered) == 1


# ── filter_by_date_range ──────────────────────────────────────────────


class TestFilterByDateRange:
    """Tests for filter_by_date_range."""

    def test_no_filters_returns_all(self):
        results = [{"date": "2024-01-01"}, {"date": "2025-01-01"}]
        assert len(filter_by_date_range(results, None, None)) == 2

    def test_start_date_filter(self):
        results = [{"date": "2023-06-01"}, {"date": "2024-06-01"}]
        filtered = filter_by_date_range(results, "2024-01-01", None)
        assert len(filtered) == 1
        assert filtered[0]["date"] == "2024-06-01"

    def test_end_date_filter(self):
        results = [{"date": "2023-06-01"}, {"date": "2024-06-01"}]
        filtered = filter_by_date_range(results, None, "2023-12-31")
        assert len(filtered) == 1

    def test_both_filters(self):
        results = [
            {"date": "2023-01-01"},
            {"date": "2024-06-15"},
            {"date": "2025-01-01"},
        ]
        filtered = filter_by_date_range(results, "2024-01-01", "2024-12-31")
        assert len(filtered) == 1

    def test_missing_date_excluded(self):
        results = [{"date": None}, {"date": "2024-06-01"}]
        filtered = filter_by_date_range(results, "2024-01-01", None)
        assert len(filtered) == 1


# ── extract_entity_mentions ───────────────────────────────────────────


class TestExtractEntityMentions:
    """Tests for extract_entity_mentions."""

    def test_empty_text(self):
        result = extract_entity_mentions("")
        assert result == {"companies": [], "sectors": [], "metrics": []}

    def test_extracts_companies(self):
        text = "$AAPL and $GOOG reported strong results"
        result = extract_entity_mentions(text)
        assert "AAPL" in result["companies"]
        assert "GOOG" in result["companies"]

    def test_extracts_sectors(self):
        text = "The technology sector saw strong growth in healthcare"
        result = extract_entity_mentions(text)
        assert "Technology" in result["sectors"]
        assert "Healthcare" in result["sectors"]

    def test_extracts_metrics(self):
        text = "Revenue grew 20% while EBITDA margins expanded. P/E is low."
        result = extract_entity_mentions(text)
        assert "revenue" in result["metrics"]
        assert "ebitda" in result["metrics"]
        assert "p/e" in result["metrics"]


# ── assemble_search_prompt ────────────────────────────────────────────


class TestAssembleSearchPrompt:
    """Tests for assemble_search_prompt."""

    def test_basic_prompt(self):
        results = [
            {"title": "Report A", "source_type": "research", "chunk_text": "Some text"},
        ]
        prompt = assemble_search_prompt("What is AAPL revenue?", results)
        assert "system_message" in prompt
        assert "user_message" in prompt
        assert "context_snippets" in prompt
        assert len(prompt["context_snippets"]) == 1

    def test_limits_to_five_results(self):
        results = [{"title": f"Doc {i}", "source_type": "news", "chunk_text": "text"} for i in range(10)]
        prompt = assemble_search_prompt("query", results)
        assert len(prompt["context_snippets"]) == 5

    def test_empty_results(self):
        prompt = assemble_search_prompt("query", [])
        assert prompt["context_snippets"] == []


# ── build_search_response ─────────────────────────────────────────────


class TestBuildSearchResponse:
    """Tests for build_search_response."""

    def test_basic_response(self):
        ranked = [
            {
                "source_type": "filing",
                "source_id": "f1",
                "title": "10-K",
                "author": "SEC",
                "date": "2024-01-01",
                "chunk_text": "$AAPL revenue grew strongly.",
                "chunk_index": 0,
                "relevance_score": 0.95,
            },
        ]
        result = build_search_response("AAPL revenue", ranked)
        assert isinstance(result, SemanticSearchResult)
        assert result.query == "AAPL revenue"
        assert len(result.results) == 1
        assert result.results[0].rank == 1
        assert result.results[0].relevance_score == 0.95

    def test_with_synthesis(self):
        ranked = [{"source_type": "news", "chunk_text": "text", "relevance_score": 0.8,
                    "source_id": "", "title": "", "author": "", "date": "", "chunk_index": 0}]
        synthesis = {"answer": "Yes", "key_themes": ["growth"], "confidence": 0.9, "data_gaps": []}
        result = build_search_response("query", ranked, synthesis)
        assert result.synthesis is not None
        assert result.synthesis.answer == "Yes"

    def test_without_synthesis(self):
        result = build_search_response("query", [])
        assert result.synthesis is None

    def test_entity_mentions_populated(self):
        ranked = [{
            "source_type": "research", "source_id": "r1", "title": "Report",
            "author": "Analyst", "date": "2024-06-01",
            "chunk_text": "$MSFT in technology sector with strong revenue growth",
            "chunk_index": 0, "relevance_score": 0.85,
        }]
        result = build_search_response("MSFT analysis", ranked)
        assert result.results[0].entity_mentions is not None
        assert "MSFT" in result.results[0].entity_mentions["companies"]

    def test_follow_ups_generated(self):
        ranked = [{
            "source_type": "news", "source_id": "n1", "title": "News",
            "author": "", "date": "", "chunk_text": "$AAPL and $GOOG rivalry",
            "chunk_index": 0, "relevance_score": 0.7,
        }]
        result = build_search_response("tech stocks", ranked)
        assert len(result.follow_ups) >= 1

    def test_empty_results(self):
        result = build_search_response("no results query", [])
        assert result.results == []
        assert len(result.follow_ups) >= 1
