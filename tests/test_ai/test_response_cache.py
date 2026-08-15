"""Tests for src/ai/response_cache.py (§6: Redis full-response cache)."""
from __future__ import annotations

import pytest

from src.ai import response_cache
from src.ai.response_cache import (
    FEATURE_CACHE_TTL,
    get_cached_structured,
    get_cached_text,
    response_cache_key,
    set_cached_structured,
    set_cached_text,
    ttl_for_feature,
)


class FakeRedisCache:
    """In-memory stand-in for src.cache.redis_cache.RedisCache -- same
    get/set/make_key surface response_cache.py actually calls."""

    def __init__(self):
        self._store: dict[str, object] = {}
        self.set_calls: list[tuple] = []
        self.get_calls: list[str] = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return self._store.get(key)

    async def set(self, key: str, value, ttl=None):
        self.set_calls.append((key, value, ttl))
        self._store[key] = value

    @staticmethod
    def make_key(*parts: str) -> str:
        return ":".join(parts)


@pytest.fixture
def fake_cache(monkeypatch):
    fake = FakeRedisCache()
    monkeypatch.setattr(response_cache, "cache", fake)
    return fake


class TestResponseCacheKey:

    def test_deterministic_for_same_inputs(self):
        k1 = response_cache_key(feature="f", model="m", system="s", user="u")
        k2 = response_cache_key(feature="f", model="m", system="s", user="u")
        assert k1 == k2

    def test_differs_when_user_input_differs(self):
        k1 = response_cache_key(feature="f", model="m", system="s", user="u1")
        k2 = response_cache_key(feature="f", model="m", system="s", user="u2")
        assert k1 != k2

    def test_differs_when_system_differs(self):
        k1 = response_cache_key(feature="f", model="m", system="s1", user="u")
        k2 = response_cache_key(feature="f", model="m", system="s2", user="u")
        assert k1 != k2

    def test_differs_when_feature_differs(self):
        k1 = response_cache_key(feature="f1", model="m", system="s", user="u")
        k2 = response_cache_key(feature="f2", model="m", system="s", user="u")
        assert k1 != k2

    def test_differs_when_model_differs(self):
        k1 = response_cache_key(feature="f", model="m1", system="s", user="u")
        k2 = response_cache_key(feature="f", model="m2", system="s", user="u")
        assert k1 != k2

    def test_none_system_does_not_collide_with_delimiter_content(self):
        # Guards against a naive string-concat key scheme where
        # feature="a" + system=None ("") could collide with a different
        # (feature, system) split producing the same concatenated string.
        k1 = response_cache_key(feature="ab", model="m", system=None, user="u")
        k2 = response_cache_key(feature="a", model="m", system="b", user="u")
        assert k1 != k2


class TestTtlForFeature:

    def test_known_feature(self):
        assert ttl_for_feature("company_primer") == FEATURE_CACHE_TTL["company_primer"]

    def test_unknown_feature_defaults_to_zero(self):
        assert ttl_for_feature("totally_unknown_feature") == 0

    def test_conversational_features_are_never_cached(self):
        assert ttl_for_feature("adviser_chat") == 0
        assert ttl_for_feature("adviser_recommendation") == 0
        assert ttl_for_feature("deep_research") == 0


@pytest.mark.asyncio
class TestTextCache:

    async def test_miss_then_set_then_hit(self, fake_cache):
        result = await get_cached_text(feature="company_primer", model="m", system="s", user="u")
        assert result is None

        await set_cached_text(feature="company_primer", model="m", system="s", user="u", text="Hello.")
        result = await get_cached_text(feature="company_primer", model="m", system="s", user="u")
        assert result == "Hello."

    async def test_uncached_feature_never_reaches_redis_on_set(self, fake_cache):
        await set_cached_text(feature="adviser_chat", model="m", system="s", user="u", text="Hello.")
        assert fake_cache.set_calls == []

    async def test_uncached_feature_get_never_reaches_redis(self, fake_cache):
        result = await get_cached_text(feature="adviser_chat", model="m", system="s", user="u")
        assert result is None
        assert fake_cache.get_calls == []

    async def test_set_uses_configured_ttl(self, fake_cache):
        await set_cached_text(feature="morning_briefing", model="m", system="s", user="u", text="x")
        assert fake_cache.set_calls[0][2] == FEATURE_CACHE_TTL["morning_briefing"]


@pytest.mark.asyncio
class TestStructuredCache:

    async def test_miss_then_set_then_hit(self, fake_cache):
        result = await get_cached_structured(feature="interpret_metric", model="m", system="s", user="u")
        assert result is None

        await set_cached_structured(
            feature="interpret_metric", model="m", system="s", user="u",
            data={"interpretation": "ROE is favorable.", "confidence": 0.8},
        )
        result = await get_cached_structured(feature="interpret_metric", model="m", system="s", user="u")
        assert result == {"interpretation": "ROE is favorable.", "confidence": 0.8}

    async def test_uncached_feature_is_always_a_miss(self, fake_cache):
        await set_cached_structured(feature="deep_research", model="m", system="s", user="u", data={"x": 1})
        result = await get_cached_structured(feature="deep_research", model="m", system="s", user="u")
        assert result is None
