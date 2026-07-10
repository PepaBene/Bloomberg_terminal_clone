"""LLM call telemetry — cost / latency / token accounting into ai_call_log.

Every call through ``src.ai.client.AIClient`` produces an :class:`AICallRecord`
which is written best-effort to the ``ai_call_log`` table. Telemetry must never
break a call: any DB failure here is swallowed. Pass ``session_factory`` to make
the write testable against an arbitrary engine.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.ai.models import estimate_cost_usd

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    """Token usage for a single call (mirrors Anthropic's usage block)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0

    @classmethod
    def from_anthropic(cls, usage: Any) -> "Usage":
        """Build from an Anthropic ``usage`` object or dict (None → zeros)."""
        if usage is None:
            return cls()

        def g(name: str) -> int:
            v = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, 0)
            try:
                return int(v or 0)
            except (TypeError, ValueError):
                return 0

        return cls(
            input_tokens=g("input_tokens"),
            output_tokens=g("output_tokens"),
            cache_write_tokens=g("cache_creation_input_tokens"),
            cache_read_tokens=g("cache_read_input_tokens"),
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )


@dataclass
class AICallRecord:
    """One row's worth of telemetry for an LLM call."""

    feature: str
    model: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    success: bool = True
    error: str | None = None
    user_id: str | None = None
    prompt_id: str | None = None
    prompt_version: int | None = None
    cost_usd: float = 0.0

    def compute_cost(self) -> float:
        self.cost_usd = estimate_cost_usd(
            self.model,
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
            cache_write_tokens=self.usage.cache_write_tokens,
            cache_read_tokens=self.usage.cache_read_tokens,
        )
        return self.cost_usd


async def record_call(rec: AICallRecord, *, session_factory: Any = None) -> None:
    """Best-effort write of a call record to ai_call_log. Never raises."""
    rec.compute_cost()
    logger.info(
        "ai_call feature=%s model=%s in=%d out=%d cache_r=%d cost=$%.5f latency=%dms ok=%s",
        rec.feature, rec.model, rec.usage.input_tokens, rec.usage.output_tokens,
        rec.usage.cache_read_tokens, rec.cost_usd, rec.latency_ms, rec.success,
    )

    factory = session_factory
    if factory is None:
        try:
            from src.database import get_session_factory

            factory = get_session_factory()
        except Exception:  # no DB configured / import failure — just log-only
            return

    try:
        from src.models.ai_call_log import AICallLog

        async with factory() as session:
            session.add(
                AICallLog(
                    id=uuid.uuid4(),
                    feature=rec.feature[:64],
                    model=rec.model[:64],
                    prompt_id=(rec.prompt_id or None),
                    prompt_version=rec.prompt_version,
                    user_id=(rec.user_id or None),
                    input_tokens=rec.usage.input_tokens,
                    output_tokens=rec.usage.output_tokens,
                    cache_write_tokens=rec.usage.cache_write_tokens,
                    cache_read_tokens=rec.usage.cache_read_tokens,
                    cost_usd=rec.cost_usd,
                    latency_ms=rec.latency_ms,
                    success=rec.success,
                    error=(rec.error[:1000] if rec.error else None),
                )
            )
            await session.commit()
    except Exception:  # telemetry must never break the caller
        logger.debug("ai_call_log write skipped", exc_info=True)


async def daily_token_usage(user_id: str, *, session_factory: Any = None) -> int:
    """Sum of tokens a user has spent today (UTC). 0 on any failure.

    Used later by the cost-budget guardrail; safe to call with no DB.
    """
    factory = session_factory
    if factory is None:
        try:
            from src.database import get_session_factory

            factory = get_session_factory()
        except Exception:
            return 0
    try:
        from sqlalchemy import func, select

        from src.models.ai_call_log import AICallLog

        async with factory() as session:
            total = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(AICallLog.input_tokens + AICallLog.output_tokens), 0
                    )
                )
                .where(AICallLog.user_id == user_id)
                .where(func.date(AICallLog.created_at) == func.current_date())
            )
            return int(total or 0)
    except Exception:
        logger.debug("daily_token_usage query skipped", exc_info=True)
        return 0
