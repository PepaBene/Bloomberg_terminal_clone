"""Thin LLM client wrapper with graceful degradation.

When ANTHROPIC_API_KEY is not set, all generate() calls return None.
This allows all endpoints to work without AI — structured data is always
returned, only narrative text fields are None.
"""

from __future__ import annotations

import logging
import os

from src.services.ai.claude_client import get_claude_client

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around LLM API with enable/disable support."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._enabled = bool(self.api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
    ) -> str | None:
        """Generate text from the LLM.

        Returns None when AI is disabled (no API key) or the call fails.
        """
        if not self._enabled:
            return None

        client = get_claude_client()
        if not client.is_configured:
            return None

        try:
            return await client.generate_text(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=max_tokens,
            )
        except Exception:
            logger.exception("LLM generation failed")
            return None


# Module-level singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the module-level LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
