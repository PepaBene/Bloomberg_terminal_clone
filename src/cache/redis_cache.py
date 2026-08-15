"""Redis caching with TTL management.

Fail-open by design: a Redis outage (or a fresh process that hasn't
called ``connect()`` yet -- e.g. under pytest, which never runs the app's
lifespan) must never break a caller that treats a cache miss as "compute
it fresh." Every public method catches connection/operational errors and
degrades to a no-op miss rather than propagating, matching this
codebase's documented failure-mode contract (AI_THREE_LAYER_REBUILD_PLAN.md
§6: "API down -> fresh cache").
"""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis wrapper with JSON serialisation and pattern-based invalidation."""

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Open a connection to the Redis server. Does not itself verify
        reachability (the client is lazy) -- a down Redis surfaces as a
        fail-open miss on the first real operation, not here."""
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self) -> None:
        """Gracefully close the Redis connection."""
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by *key*, returning ``None`` on miss
        (including "Redis unreachable")."""
        if not self._redis:
            return None
        try:
            data = await self._redis.get(key)
        except Exception:
            logger.warning("redis GET failed for key=%s -- treating as a miss", key, exc_info=True)
            return None
        return json.loads(data) if data else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store *value* under *key* with an optional TTL in seconds.
        Silently no-ops on a Redis failure -- a write that's lost just
        means the next read recomputes, not a caller-visible error."""
        if not self._redis:
            return
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            logger.warning("redis SET failed for key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        """Remove a single cache entry."""
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            logger.warning("redis DELETE failed for key=%s", key, exc_info=True)

    async def delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching a glob *pattern* (e.g. ``entity:*``)."""
        if not self._redis:
            return
        try:
            keys: list[str] = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
        except Exception:
            logger.warning("redis DELETE_PATTERN failed for pattern=%s", pattern, exc_info=True)

    @staticmethod
    def make_key(*parts: str) -> str:
        """Build a colon-separated cache key from *parts*."""
        return ":".join(parts)

    @staticmethod
    def hash_params(**params: Any) -> str:
        """Return a short deterministic hash of the given parameters."""
        filtered = {k: v for k, v in sorted(params.items()) if v is not None}
        return hashlib.md5(json.dumps(filtered).encode()).hexdigest()[:12]


cache = RedisCache()
