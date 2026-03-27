"""Google Gemini Embedding 2 client for semantic search."""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-002"
DEFAULT_DIMENSIONS = 3072
MAX_BATCH_SIZE = 100

TASK_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
TASK_SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
TASK_CLASSIFICATION = "CLASSIFICATION"
TASK_CODE_RETRIEVAL = "CODE_RETRIEVAL"


@dataclass
class EmbeddingResult:
    embedding: list[float]
    dimensions: int
    model: str
    token_count: int | None = None


class EmbeddingClient:
    """Client for Google Gemini Embedding 2 (multimodal)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._client = None
        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                logger.warning("google-genai not installed: pip install google-genai>=1.0.0")

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def embed_text(
        self,
        text: str,
        dimensions: int = DEFAULT_DIMENSIONS,
        task_type: str = TASK_RETRIEVAL_DOCUMENT,
    ) -> EmbeddingResult:
        if not self._client:
            raise RuntimeError("Embedding client not configured. Set GOOGLE_API_KEY.")
        from google.genai import types
        result = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=dimensions,
            ),
        )
        embedding = result.embeddings[0].values
        return EmbeddingResult(
            embedding=embedding,
            dimensions=len(embedding),
            model=EMBEDDING_MODEL,
        )

    def embed_batch(
        self,
        texts: list[str],
        dimensions: int = DEFAULT_DIMENSIONS,
        task_type: str = TASK_RETRIEVAL_DOCUMENT,
    ) -> list[EmbeddingResult]:
        if not self._client:
            raise RuntimeError("Embedding client not configured.")
        from google.genai import types
        results = []
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i:i + MAX_BATCH_SIZE]
            response = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=dimensions,
                ),
            )
            for emb in response.embeddings:
                results.append(EmbeddingResult(
                    embedding=emb.values,
                    dimensions=len(emb.values),
                    model=EMBEDDING_MODEL,
                ))
        return results

    def embed_for_query(
        self,
        query: str,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> EmbeddingResult:
        return self.embed_text(query, dimensions, task_type=TASK_RETRIEVAL_QUERY)


_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
