"""Tests for src/cache/redis_cache.py's fail-open behavior (§6): a Redis
connection failure must degrade to a cache miss / silent no-op, never
propagate to the caller."""
from __future__ import annotations

import pytest

from src.cache.redis_cache import RedisCache


class _RaisingRedis:
    async def get(self, key):
        raise ConnectionError("redis unreachable")

    async def set(self, key, value, ex=None):
        raise ConnectionError("redis unreachable")

    async def delete(self, *keys):
        raise ConnectionError("redis unreachable")

    def scan_iter(self, match=None):
        raise ConnectionError("redis unreachable")


class _WorkingRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)

    async def scan_iter(self, match=None):
        for k in list(self._store.keys()):
            yield k


@pytest.mark.asyncio
class TestNotConnected:
    """Before connect() is ever called (e.g. under pytest, which never
    runs the app lifespan), every method is a silent no-op."""

    async def test_get_returns_none(self):
        cache = RedisCache()
        assert await cache.get("k") is None

    async def test_set_does_not_raise(self):
        cache = RedisCache()
        await cache.set("k", {"a": 1})  # should not raise

    async def test_delete_does_not_raise(self):
        cache = RedisCache()
        await cache.delete("k")

    async def test_delete_pattern_does_not_raise(self):
        cache = RedisCache()
        await cache.delete_pattern("k:*")


@pytest.mark.asyncio
class TestFailOpenOnConnectionError:

    async def test_get_fails_open(self):
        cache = RedisCache()
        cache._redis = _RaisingRedis()
        assert await cache.get("k") is None

    async def test_set_fails_open(self):
        cache = RedisCache()
        cache._redis = _RaisingRedis()
        await cache.set("k", {"a": 1})  # should not raise

    async def test_delete_fails_open(self):
        cache = RedisCache()
        cache._redis = _RaisingRedis()
        await cache.delete("k")

    async def test_delete_pattern_fails_open(self):
        cache = RedisCache()
        cache._redis = _RaisingRedis()
        await cache.delete_pattern("k:*")


@pytest.mark.asyncio
class TestWorkingRoundTrip:

    async def test_get_set_round_trip(self):
        cache = RedisCache()
        cache._redis = _WorkingRedis()
        assert await cache.get("k") is None
        await cache.set("k", {"a": 1}, ttl=60)
        assert await cache.get("k") == {"a": 1}

    async def test_delete(self):
        cache = RedisCache()
        cache._redis = _WorkingRedis()
        await cache.set("k", {"a": 1})
        await cache.delete("k")
        assert await cache.get("k") is None


class TestPureHelpers:

    def test_make_key(self):
        assert RedisCache.make_key("a", "b", "c") == "a:b:c"

    def test_hash_params_deterministic(self):
        h1 = RedisCache.hash_params(x=1, y=2)
        h2 = RedisCache.hash_params(y=2, x=1)
        assert h1 == h2

    def test_hash_params_ignores_none_values(self):
        h1 = RedisCache.hash_params(x=1, y=None)
        h2 = RedisCache.hash_params(x=1)
        assert h1 == h2
