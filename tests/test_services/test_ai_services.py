"""Tests for AI service layer — all API calls mocked.

``vector_search.py`` and ``claude_client.py`` were retired once
``src/ai/retrieval/`` and ``src/ai/client.py`` replaced them (see
AI_THREE_LAYER_REBUILD_PLAN.md's Phase 0 build log) -- their coverage now
lives in ``tests/test_ai/test_retrieval.py`` (chunking) and
``tests/test_ai/test_ai_core.py`` (the Claude client). Only
``embedding_client.py`` is still live here.
"""
from unittest.mock import patch


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
