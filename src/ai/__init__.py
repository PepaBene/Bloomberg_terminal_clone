"""AI core for the three-layer stack (interpreter / news / adviser).

Public surface:
    from src.ai import get_ai_client, Tier, tier_for, load_prompt
    from src.ai import get_llm_client   # legacy compatibility facade
    from src.ai.retrieval import chunk_text, embed_documents, hybrid_search
"""
from src.ai.client import AIClient, AIResponse, get_ai_client
from src.ai.llm_client import LLMClient, get_llm_client
from src.ai.models import Tier, estimate_cost_usd, model_for_tier
from src.ai.prompts import Prompt, list_prompts, load_prompt
from src.ai.router import tier_for

__all__ = [
    "AIClient",
    "AIResponse",
    "get_ai_client",
    "LLMClient",
    "get_llm_client",
    "Tier",
    "model_for_tier",
    "estimate_cost_usd",
    "tier_for",
    "Prompt",
    "load_prompt",
    "list_prompts",
]
