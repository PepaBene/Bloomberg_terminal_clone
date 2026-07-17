"""Backwards-compatible thin LLM wrapper over the new AI core.

Preserves the historical interface the API routers rely on::

    llm = get_llm_client()
    if llm.enabled:
        text = await llm.generate(system_prompt, user_prompt)

``generate`` returns ``None`` when AI is disabled (no key / package) or the call
fails, so every endpoint keeps working without an API key. New code should use
``src.ai.client.get_ai_client()`` directly for streaming / structured output.
"""
from __future__ import annotations

import logging

from src.ai.client import get_ai_client

logger = logging.getLogger(__name__)


class LLMClient:
    """Compatibility facade over :class:`src.ai.client.AIClient`."""

    def __init__(self):
        self._client = get_ai_client()

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    @property
    def api_key(self) -> str:
        return self._client.api_key

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        *,
        feature: str = "legacy_narrative",
        user_id: str | None = None,
    ) -> str | None:
        """Generate text; returns None when AI is disabled or the call fails."""
        return await self._client.complete_text(
            user=user_prompt,
            system=system_prompt,
            max_tokens=max_tokens,
            feature=feature,
            user_id=user_id,
        )


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the module-level LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
