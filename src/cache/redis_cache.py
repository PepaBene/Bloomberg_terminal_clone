"""Redis caching with TTL management."""

import hashlib
import json
from typing import Any

import redis.asyncio as redis

from src.config import settings


class RedisCache:
    """Async Redis wrapper with JSON serialisation and pattern-based invalidation."""

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Open a connection to the Redis server."""
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self) -> None:
        """Gracefully close the Redis connection."""
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by *key*, returning ``None`` on miss."""
        if not self._redis:
            return None
        data = await self._redis.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store *value* under *key* with an optional TTL in seconds."""
        if not self._redis:
            return
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        """Remove a single cache entry."""
        if not self._redis:
            return
        await self._redis.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching a glob *pattern* (e.g. ``entity:*``)."""
        if not self._redis:
            return
        keys: list[str] = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)

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
