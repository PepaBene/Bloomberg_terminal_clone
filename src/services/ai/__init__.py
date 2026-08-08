"""Legacy AI service layer.

``claude_client.py`` and ``vector_search.py`` have been retired: the 9
narrative routers that used to import ``get_llm_client``/inline prompts
(and ``guidance_extraction.py``'s optional AI augmentation pass, which used
``claude_client`` directly) now go through the new AI core
(``src/ai/client.py``'s ``AIClient`` + ``src/ai/prompts``'s registry) --
see AI_THREE_LAYER_REBUILD_PLAN.md's Phase 0 build log. ``vector_search.py``
was already dead in production (only test-referenced) once
``src/ai/retrieval/`` shipped its own chunker/store/retriever.

``embedding_client.py`` stays: it's still the live Gemini
``gemini-embedding-002`` wrapper, used directly by both
``src/ai/retrieval/embedder.py`` and ``src/api/routers/research_search.py``.
"""
from src.services.ai.embedding_client import EmbeddingClient, get_embedding_client

__all__ = ["EmbeddingClient", "get_embedding_client"]
