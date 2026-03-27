"""Tests for AI service layer — all API calls mocked."""
import pytest
import math
from unittest.mock import patch

from src.services.ai.vector_search import (
    cosine_similarity,
    euclidean_distance,
    normalize_vector,
    top_k_similar,
    rerank_by_recency,
    chunk_text,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        score = cosine_similarity([1, 2, 3], [1, 2, 4])
        assert 0.9 < score < 1.0

    def test_zero_vector(self):
        assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_dimension_mismatch(self):
        with pytest.raises(ValueError):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_high_dimensional(self):
        a = [float(i) for i in range(100)]
        score = cosine_similarity(a, a)
        assert score == pytest.approx(1.0)


class TestEuclideanDistance:
    def test_same_point(self):
        assert euclidean_distance([1, 2], [1, 2]) == 0.0

    def test_simple_distance(self):
        assert euclidean_distance([0, 0], [3, 4]) == pytest.approx(5.0)

    def test_dimension_mismatch(self):
        with pytest.raises(ValueError):
            euclidean_distance([1], [1, 2])

    def test_negative_coords(self):
        d = euclidean_distance([-1, -1], [1, 1])
        assert d == pytest.approx(2 * math.sqrt(2))


class TestNormalizeVector:
    def test_unit_vector_unchanged(self):
        result = normalize_vector([1, 0, 0])
        assert result == pytest.approx([1, 0, 0])

    def test_normalize_to_unit(self):
        result = normalize_vector([3, 4])
        norm = math.sqrt(sum(v * v for v in result))
        assert norm == pytest.approx(1.0)

    def test_zero_vector(self):
        assert normalize_vector([0, 0, 0]) == [0, 0, 0]

    def test_negative_values(self):
        result = normalize_vector([-3, 4])
        norm = math.sqrt(sum(v * v for v in result))
        assert norm == pytest.approx(1.0)
        assert result[0] < 0


class TestTopKSimilar:
    def test_finds_most_similar(self):
        query = [1.0, 0.0, 0.0]
        candidates = [
            ("doc1", [1.0, 0.0, 0.0]),
            ("doc2", [0.0, 1.0, 0.0]),
            ("doc3", [0.9, 0.1, 0.0]),
        ]
        results = top_k_similar(query, candidates, k=2)
        assert len(results) == 2
        assert results[0].document_id == "doc1"
        assert results[0].similarity_score == pytest.approx(1.0)

    def test_k_larger_than_candidates(self):
        results = top_k_similar([1, 0], [("a", [1, 0])], k=5)
        assert len(results) == 1

    def test_empty_candidates(self):
        results = top_k_similar([1, 0], [], k=5)
        assert len(results) == 0

    def test_ordering_correct(self):
        query = [1.0, 0.0]
        candidates = [
            ("worst", [0.0, 1.0]),
            ("best", [1.0, 0.0]),
            ("mid", [0.7, 0.7]),
        ]
        results = top_k_similar(query, candidates, k=3)
        assert results[0].document_id == "best"
        assert results[-1].document_id == "worst"


class TestRerankByRecency:
    def test_recency_boost(self):
        results = [
            {"relevance_score": 0.8, "age_days": 365},
            {"relevance_score": 0.7, "age_days": 1},
        ]
        reranked = rerank_by_recency(results, recency_weight=0.3)
        assert reranked[0]["age_days"] == 1

    def test_zero_weight_preserves_order(self):
        results = [
            {"relevance_score": 0.9, "age_days": 365},
            {"relevance_score": 0.5, "age_days": 1},
        ]
        reranked = rerank_by_recency(results, recency_weight=0.0)
        assert reranked[0]["relevance_score"] == 0.9

    def test_very_old_no_bonus(self):
        results = [{"relevance_score": 0.5, "age_days": 9999}]
        reranked = rerank_by_recency(results, recency_weight=0.1)
        assert reranked[0]["combined_score"] <= 0.5


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("Short text.", max_tokens=100)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_paragraph_splitting(self):
        text = "Para one. " * 50 + "\n\n" + "Para two. " * 50
        chunks = chunk_text(text, max_tokens=100)
        assert len(chunks) >= 2

    def test_empty_text(self):
        chunks = chunk_text("", max_tokens=100)
        assert len(chunks) == 0

    def test_single_long_paragraph(self):
        text = "Word " * 500
        chunks = chunk_text(text, max_tokens=50)
        assert len(chunks) > 1

    def test_preserves_content(self):
        text = "Hello world.\n\nSecond paragraph."
        chunks = chunk_text(text, max_tokens=1000)
        assert len(chunks) == 1
        assert "Hello world." in chunks[0]
        assert "Second paragraph." in chunks[0]


class TestClaudeClient:
    def test_not_configured_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from src.services.ai.claude_client import ClaudeClient
            client = ClaudeClient(api_key="")
            assert not client.is_configured

    def test_configured_detection(self):
        from src.services.ai.claude_client import ClaudeClient, CLAUDE_MODEL
        assert CLAUDE_MODEL == "claude-sonnet-4-6"


class TestEmbeddingClient:
    def test_not_configured_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from src.services.ai.embedding_client import EmbeddingClient
            client = EmbeddingClient(api_key="")
            assert not client.is_configured

    def test_model_constants(self):
        from src.services.ai.embedding_client import (
            EMBEDDING_MODEL, DEFAULT_DIMENSIONS,
            TASK_RETRIEVAL_DOCUMENT, TASK_RETRIEVAL_QUERY,
        )
        assert EMBEDDING_MODEL == "gemini-embedding-002"
        assert DEFAULT_DIMENSIONS == 3072
        assert TASK_RETRIEVAL_DOCUMENT == "RETRIEVAL_DOCUMENT"
        assert TASK_RETRIEVAL_QUERY == "RETRIEVAL_QUERY"
