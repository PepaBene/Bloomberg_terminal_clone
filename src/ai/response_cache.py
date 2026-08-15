"""AI_THREE_LAYER_REBUILD_PLAN.md §6: "Redis full-response cache keyed on
sha256(prompt_id+version+inputs) with per-feature TTL."

This is a SEPARATE layer from Anthropic's own prompt caching
(``AIClient._system_param``'s ``cache_control: ephemeral``, already
wired since Phase 0) -- that discounts token cost on a cache hit but
still makes a real API call every time; this layer skips the API call
entirely on a hit.

The key is ``sha256(feature + model + system + user)`` rather than the
plan's literal ``prompt_id + version + inputs``: ``system`` already IS
the rendered prompt text (changes whenever the prompt or its version
changes) and ``user`` already IS the rendered inputs, so hashing those
directly achieves the same "identical prompt + identical inputs ->
identical cache key" property without requiring every one of this
codebase's existing ``complete_text``/``complete_structured`` call sites
to additionally thread through an explicit ``prompt_id``/``version``
(most already pass ``system=prompt.system, user=prompt.render(...)``
from the prompt registry, so this is equivalent in practice for prompts
loaded that way, and still correct -- just coarser-grained -- for ad hoc
system/user text).

Deliberately applied only to ``complete_text``/``complete_structured``
(single-shot "final answer" calls), never to the raw multi-turn
``complete()`` an agent loop drives directly -- caching one turn of a
dynamic tool-use conversation by its raw message content would be both
useless (message histories are unique per conversation) and wrong (a
cached tool-loop response wouldn't necessarily still make sense
mid-conversation).
"""
from __future__ import annotations

import hashlib

from src.cache.redis_cache import cache

CACHE_KEY_PREFIX = "ai_response"

# Per-feature TTL in seconds. Absent or 0 means "don't cache" -- the
# conservative default for anything not explicitly reasoned about below,
# since serving a stale AI response silently is a worse failure mode than
# an extra API call.
FEATURE_CACHE_TTL: dict[str, int] = {
    # Layer 1 — Interpreter: these already have their own Postgres
    # compute-on-miss cache (src/ai/interpret/store.py) keyed on
    # analytics_version, so this layer mostly guards against duplicate
    # concurrent computes of the exact same (uncached) metric, not
    # repeat reads -- short TTL is enough for that.
    "interpret_metric": 900,
    "interpret_subject": 900,
    # Layer 2 — News/Information: same story, own Postgres cache in
    # src/ai/news/store.py (ai_analysis/cluster_analysis columns).
    "news_article_summary": 900,
    "news_cluster_analysis": 900,
    "sentiment_score": 3600,
    # Legacy narrative features migrated in Phase 0 -- no persistent
    # cache of their own, so this is their only response cache.
    "company_primer": 3600,
    "company_briefing": 3600,
    "morning_briefing": 1800,
    "investment_thesis": 3600,
    "investment_thesis_pitch": 3600,
    "earnings_narrative": 3600,
    "rating_narrative": 3600,
    "legacy_narrative": 1800,
    "guidance_extraction": 3600,
    # Layer 3 — Adviser: conversational and stateful (portfolio state
    # changes between calls, and a cached reply would be reasoning about
    # stale holdings) -- never cached. Deep Research is its own
    # Postgres-backed job record already; re-running it is meant to be a
    # deliberate, fresh action, not silently served from cache.
    "adviser_chat": 0,
    "adviser_recommendation": 0,
    "deep_research": 0,
    # research_qa.py's single-shot Q&A has no persistent cache of its
    # own and isn't conversational in the adviser sense -- cache briefly.
    "analyst_qa": 900,
}
DEFAULT_CACHE_TTL = 0


def response_cache_key(*, feature: str, model: str, system: str | None, user: str) -> str:
    """Pure: the sha256-based cache key described in the module docstring."""
    digest = hashlib.sha256(
        "\x1f".join([feature, model, system or "", user]).encode("utf-8")
    ).hexdigest()
    return cache.make_key(CACHE_KEY_PREFIX, feature, digest)


def ttl_for_feature(feature: str) -> int:
    return FEATURE_CACHE_TTL.get(feature, DEFAULT_CACHE_TTL)


async def get_cached_text(*, feature: str, model: str, system: str | None, user: str) -> str | None:
    """``None`` on a miss OR when this feature isn't configured to cache
    at all -- callers don't need to check ``ttl_for_feature`` separately."""
    if ttl_for_feature(feature) <= 0:
        return None
    key = response_cache_key(feature=feature, model=model, system=system, user=user)
    cached = await cache.get(key)
    return cached.get("text") if isinstance(cached, dict) else None


async def set_cached_text(*, feature: str, model: str, system: str | None, user: str, text: str) -> None:
    ttl = ttl_for_feature(feature)
    if ttl <= 0:
        return
    key = response_cache_key(feature=feature, model=model, system=system, user=user)
    await cache.set(key, {"text": text}, ttl=ttl)


async def get_cached_structured(*, feature: str, model: str, system: str | None, user: str) -> dict | None:
    """Returns the raw cached dict (caller re-validates through their own
    Pydantic model) -- ``None`` on a miss or an uncached feature."""
    if ttl_for_feature(feature) <= 0:
        return None
    key = response_cache_key(feature=feature, model=model, system=system, user=user)
    cached = await cache.get(key)
    return cached.get("data") if isinstance(cached, dict) else None


async def set_cached_structured(*, feature: str, model: str, system: str | None, user: str, data: dict) -> None:
    ttl = ttl_for_feature(feature)
    if ttl <= 0:
        return
    key = response_cache_key(feature=feature, model=model, system=system, user=user)
    await cache.set(key, {"data": data}, ttl=ttl)
