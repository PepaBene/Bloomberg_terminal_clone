"""Thin LLM client wrapper with graceful degradation.

When ANTHROPIC_API_KEY is not set, all generate() calls return None.
This allows all endpoints to work without AI — structured data is always
returned, only narrative text fields are None.
"""

from __future__ import annotations

import os


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

        Returns None when AI is disabled (no API key).
        """
        if not self._enabled:
            return None

        # In production, this would call the Anthropic API.
        # For now, return None to indicate AI is available but
        # actual integration is deferred.
        return None


# Module-level singleton
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the module-level LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
