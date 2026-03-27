"""Claude Sonnet 4.6 client for AI-powered research features."""
from __future__ import annotations

import os
import logging
from typing import TypeVar, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3


class ClaudeClient:
    """Async client for Claude Sonnet 4.6 structured generation."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        self._sync_client = None
        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
                self._sync_client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("anthropic package not installed: pip install anthropic>=0.79.0")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key) and self._client is not None

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> T:
        if not self._client:
            raise RuntimeError("Claude client not configured. Set ANTHROPIC_API_KEY.")
        response = await self._client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a Bloomberg financial research AI assistant.",
            messages=[{"role": "user", "content": prompt}],
            response_format=response_model,
        )
        return response.parsed

    async def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        if not self._client:
            raise RuntimeError("Claude client not configured. Set ANTHROPIC_API_KEY.")
        response = await self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a Bloomberg financial research AI assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def generate_structured_sync(
        self,
        prompt: str,
        response_model: Type[T],
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> T:
        if not self._sync_client:
            raise RuntimeError("Claude client not configured. Set ANTHROPIC_API_KEY.")
        response = self._sync_client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a Bloomberg financial research AI assistant.",
            messages=[{"role": "user", "content": prompt}],
            response_format=response_model,
        )
        return response.parsed


_claude_client: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    global _claude_client
    if _claude_client is None:
        _claude_client = ClaudeClient()
    return _claude_client
