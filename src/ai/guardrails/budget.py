"""Per-user daily token budget enforcement.

Reuses ``telemetry.daily_token_usage()`` (already sums today's tokens per
user from ``ai_call_log`` -- its own docstring flagged it as built "for the
budget guardrail"). Default ceiling matches AI_THREE_LAYER_REBUILD_PLAN.md
§6 / the superseded plan's decided default: 10M tokens/user/day on
Sonnet/Opus, unlimited on Haiku -- light-tier calls (per-metric
interpretations, alert summaries) are cheap and meant to run at volume;
budgeting them would defeat their purpose.

Callers (an API route, before invoking the agent loop) should catch
``BudgetExceededError`` and return 429 with a ``Retry-After`` header.
"""
from __future__ import annotations

from typing import Any

from src.ai.models import Tier
from src.ai.telemetry import daily_token_usage

DEFAULT_DAILY_TOKEN_BUDGET = 10_000_000


class BudgetExceededError(Exception):
    def __init__(self, user_id: str, used: int, limit: int):
        self.user_id = user_id
        self.used = used
        self.limit = limit
        super().__init__(
            f"user {user_id!r} has used {used} tokens today, over the {limit} daily budget"
        )


def _is_light(tier: Tier | str) -> bool:
    try:
        return Tier(tier) is Tier.LIGHT
    except ValueError:
        return False


async def check_budget(
    user_id: str | None,
    *,
    tier: Tier | str = Tier.SYNTHESIS,
    limit: int = DEFAULT_DAILY_TOKEN_BUDGET,
    session_factory: Any = None,
) -> None:
    """Raise ``BudgetExceededError`` if ``user_id`` is already at/over budget.

    No-ops (never raises) for: light-tier calls, calls with no user context
    (system/batch jobs have nothing to budget against), or if the usage
    lookup itself fails (``daily_token_usage`` already degrades to 0 on any
    DB error rather than raising -- this function inherits that fail-open
    behavior deliberately, since a telemetry outage must not take down the
    AI features it's supposed to be observing).
    """
    if not user_id or _is_light(tier):
        return
    used = await daily_token_usage(user_id, session_factory=session_factory)
    if used >= limit:
        raise BudgetExceededError(user_id, used, limit)
