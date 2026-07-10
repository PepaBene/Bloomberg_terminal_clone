"""Unified async Anthropic client for the AI core.

Replaces the single-method ``src/services/ai/claude_client.py`` with a client
that supports:

* plain text completion (``complete_text``)
* tool-forced **structured** output validated by a Pydantic model
  (``complete_structured``) — robust across SDK versions, unlike the old
  ``messages.parse(response_format=...)`` path
* token streaming (``stream``) for SSE endpoints
* prompt caching, model tiering, retry/backoff, and per-call telemetry

It preserves the platform's graceful-degradation contract: when
``ANTHROPIC_API_KEY`` is unset **or** the ``anthropic`` package is not
installed, ``enabled`` is ``False``, ``complete_text``/``stream`` no-op, and the
structured/raw methods raise ``RuntimeError`` (callers should check ``enabled``).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from src.ai.models import DEFAULT_TIER, Tier, model_for_tier
from src.ai.telemetry import AICallRecord, Usage, record_call

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.3
MAX_RETRIES = 3

_RETRYABLE_NAMES = {
    "RateLimitError", "APITimeoutError", "APIConnectionError",
    "InternalServerError", "OverloadedError", "APIStatusError",
}
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 529}


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if type(exc).__name__ in _RETRYABLE_NAMES:
        # A typed status error carries a code — honor it (don't retry a 400).
        return status in _RETRYABLE_STATUS if status is not None else True
    return status in _RETRYABLE_STATUS


@dataclass
class AIResponse:
    """Normalized view of an Anthropic message response."""

    text: str
    tool_uses: list[Any] = field(default_factory=list)
    stop_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    raw: Any = None

    @classmethod
    def from_raw(cls, raw: Any) -> "AIResponse":
        text_parts: list[str] = []
        tools: list[Any] = []
        for block in (getattr(raw, "content", None) or []):
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif btype == "tool_use":
                tools.append(block)
        return cls(
            text="".join(text_parts),
            tool_uses=tools,
            stop_reason=getattr(raw, "stop_reason", None),
            usage=Usage.from_anthropic(getattr(raw, "usage", None)),
            model=getattr(raw, "model", "") or "",
            raw=raw,
        )


class AIClient:
    def __init__(self, api_key: str | None = None):
        if api_key is None:
            try:
                from src.config import settings

                api_key = settings.ANTHROPIC_API_KEY or ""
            except Exception:
                api_key = ""
            if not api_key:
                import os

                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._api_key = api_key or ""
        self._client = None
        if self._api_key:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                logger.warning(
                    "anthropic package not installed — AI disabled. pip install 'anthropic>=0.40'"
                )
            except Exception:
                logger.exception("failed to init Anthropic client — AI disabled")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def api_key(self) -> str:
        return self._api_key

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _system_param(system: str | None, cache: bool):
        if not system:
            return None
        if not cache:
            return system
        # Mark large system prompts cacheable for ~10x cost reduction on repeats.
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    async def _with_retry(self, make_coro, *, feature: str):
        delay = 0.5
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await make_coro()
            except Exception as e:  # noqa: BLE001
                if attempt < MAX_RETRIES and _is_retryable(e):
                    logger.warning(
                        "ai retry %d/%d for %s: %s", attempt + 1, MAX_RETRIES, feature, e
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    async def complete(
        self,
        *,
        user: str | None = None,
        messages: list[dict] | None = None,
        system: str | None = None,
        tier: Tier | str = DEFAULT_TIER,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        feature: str = "generic",
        cache_system: bool = True,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        user_id: str | None = None,
        prompt_id: str | None = None,
        prompt_version: int | None = None,
    ) -> AIResponse:
        """Full completion returning text + any tool_use blocks + usage."""
        if self._client is None:
            raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
        model = model or model_for_tier(tier)
        if messages is None:
            if user is None:
                raise ValueError("complete() requires `user` or `messages`")
            messages = [{"role": "user", "content": user}]

        kwargs: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, temperature=temperature, messages=messages
        )
        sys_param = self._system_param(system, cache_system)
        if sys_param is not None:
            kwargs["system"] = sys_param
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        t0 = time.monotonic()
        raw = None
        success = True
        error: str | None = None
        try:
            raw = await self._with_retry(
                lambda: self._client.messages.create(**kwargs), feature=feature
            )
            return AIResponse.from_raw(raw)
        except Exception as e:  # noqa: BLE001
            success = False
            error = f"{type(e).__name__}: {e}"
            raise
        finally:
            latency = int((time.monotonic() - t0) * 1000)
            usage = Usage.from_anthropic(getattr(raw, "usage", None)) if raw is not None else Usage()
            rec = AICallRecord(
                feature=feature, model=model, usage=usage, latency_ms=latency,
                success=success, error=error, user_id=user_id,
                prompt_id=prompt_id, prompt_version=prompt_version,
            )
            try:
                await record_call(rec)
            except Exception:  # pragma: no cover - defensive
                logger.debug("telemetry record failed", exc_info=True)

    async def complete_text(
        self,
        *,
        user: str,
        system: str | None = None,
        tier: Tier | str = DEFAULT_TIER,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        feature: str = "generic",
        cache_system: bool = True,
        user_id: str | None = None,
    ) -> str | None:
        """Text-only helper. Returns None when disabled or on failure."""
        if self._client is None:
            return None
        try:
            resp = await self.complete(
                user=user, system=system, tier=tier, model=model, max_tokens=max_tokens,
                temperature=temperature, feature=feature, cache_system=cache_system,
                user_id=user_id,
            )
            return resp.text or None
        except Exception:
            logger.exception("complete_text failed (feature=%s)", feature)
            return None

    async def complete_structured(
        self,
        *,
        response_model: type[T],
        user: str,
        system: str | None = None,
        tier: Tier | str = DEFAULT_TIER,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 0.2,
        feature: str = "structured",
        cache_system: bool = True,
        user_id: str | None = None,
    ) -> T:
        """Force the model to emit JSON matching ``response_model`` (tool_use)."""
        if self._client is None:
            raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
        tool_name = f"emit_{response_model.__name__}"
        tool = {
            "name": tool_name,
            "description": f"Return the answer as a {response_model.__name__} object.",
            "input_schema": response_model.model_json_schema(),
        }
        resp = await self.complete(
            user=user, system=system, tier=tier, model=model, max_tokens=max_tokens,
            temperature=temperature, feature=feature, cache_system=cache_system,
            tools=[tool], tool_choice={"type": "tool", "name": tool_name}, user_id=user_id,
        )
        for block in resp.tool_uses:
            if getattr(block, "name", None) == tool_name:
                return response_model.model_validate(getattr(block, "input", {}) or {})
        raise ValueError(f"structured output missing for {response_model.__name__}")

    async def stream(
        self,
        *,
        user: str,
        system: str | None = None,
        tier: Tier | str = DEFAULT_TIER,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        feature: str = "stream",
        cache_system: bool = True,
        user_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas. When disabled, yields nothing."""
        if self._client is None:
            return
        model = model or model_for_tier(tier)
        kwargs: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        sys_param = self._system_param(system, cache_system)
        if sys_param is not None:
            kwargs["system"] = sys_param

        t0 = time.monotonic()
        raw_final = None
        success = True
        error: str | None = None
        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
                raw_final = await stream.get_final_message()
        except Exception as e:  # noqa: BLE001
            success = False
            error = f"{type(e).__name__}: {e}"
            logger.exception("stream failed (feature=%s)", feature)
            raise
        finally:
            latency = int((time.monotonic() - t0) * 1000)
            usage = (
                Usage.from_anthropic(getattr(raw_final, "usage", None))
                if raw_final is not None
                else Usage()
            )
            rec = AICallRecord(
                feature=feature, model=model, usage=usage, latency_ms=latency,
                success=success, error=error, user_id=user_id,
            )
            try:
                await record_call(rec)
            except Exception:  # pragma: no cover - defensive
                logger.debug("telemetry record failed", exc_info=True)


_ai_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """Module-level singleton."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
