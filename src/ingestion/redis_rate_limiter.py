"""Redis-backed distributed rate limiter for external API calls shared across
OS processes.

The plain in-process ``RateLimiter`` (src/ingestion/rate_limiter.py) only
throttles requests within one Python process. It cannot coordinate across
process boundaries -- and this codebase routinely runs several: 2 concurrent
``scripts.backfill`` subprocesses plus ``scripts.run_extra_ingestion``'s SEC
EDGAR stage, each with its OWN independent SEC rate limiter believing it
alone owns SEC's full 10 req/sec budget. With ~10+ SEC-touching connector
types simultaneously active (e.g. during a stale-data refresh), the
aggregate request rate stacks well past what SEC actually tolerates from one
IP, causing a sustained 429 storm that no single connector's own limiter
can see or prevent.

This uses a Redis-backed token bucket (atomic via a Lua script, so
concurrent processes never race on the read-modify-write) with virtual
scheduling: ``acquire()`` reserves a slot and returns how long the caller
must wait before actually making the request, rather than blocking inside
Redis itself. Every process/connector sharing the same ``key`` draws from
the same bucket, so the aggregate rate across the whole machine is capped
at ``max_requests / per_seconds`` regardless of how many processes or
connector instances are running concurrently.

Fails OPEN: if Redis is unreachable, requests proceed unthrottled (with a
rate-limited warning log) rather than blocking ingestion entirely on a
Redis outage. This is a good-citizen throttle, not a security control --
better to occasionally risk a 429 than to hard-fail every connector because
Redis hiccuped.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time

import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)

# Lua script implementing GCRA (Generic Cell Rate Algorithm) -- NOT a naive
# token bucket. A naive bucket (store "tokens remaining", refill by elapsed
# wall-clock time) is wrong for *virtual scheduling* under concurrency: when
# a request is denied an immediate slot and told to wait, the bucket must
# reserve that future slot for it, or a second concurrent caller computing
# against the same "now" will be handed the SAME slot (verified live: a
# naive-bucket version of this script let 3 concurrent callers blow straight
# through a 5 req/sec cap at ~16 req/sec effective). GCRA tracks a single
# "theoretical arrival time" (TAT) in Redis -- when the bucket is next free
# -- and every request atomically reads it, computes its own wait as
# ``TAT - now``, then advances TAT by one emission interval for whoever
# calls next. That forward-advance IS the reservation, so concurrent callers
# correctly queue behind each other regardless of process/instance count.
# Returns the wait time in MILLISECONDS (integer) -- Redis truncates Lua
# floats to integers on return, so fractional seconds would lose precision.
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local emission_interval = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

local tat = tonumber(redis.call('GET', key))
if tat == nil or tat < now then
    tat = now
end

local wait = tat - now
local new_tat = tat + emission_interval

redis.call('SET', key, tostring(new_tat), 'EX', 60)

return math.ceil(wait * 1000)
"""

# One shared client + script registration per process, keyed by redis_url --
# every RedisRateLimiter instance in a process reuses it rather than opening
# a new connection per connector.
_clients: dict[str, redis.Redis] = {}
_scripts: dict[str, "redis.commands.core.Script"] = {}
_warned_fallback = False


async def _get_script(redis_url: str):
    if redis_url not in _scripts:
        client = redis.from_url(redis_url, decode_responses=True, socket_timeout=2.0)
        _clients[redis_url] = client
        _scripts[redis_url] = client.register_script(_TOKEN_BUCKET_SCRIPT)
    return _scripts[redis_url]


class RedisRateLimiter:
    """Distributed token-bucket rate limiter, shared across all processes
    that construct one with the same ``key``.

    Drop-in replacement for ``RateLimiter`` -- same ``acquire()`` /
    ``async with`` interface -- but ``key`` (not just the local instance)
    determines which bucket is shared. Use the same key (e.g.
    ``"sec_edgar"``) across every connector that should share one budget.
    """

    def __init__(
        self,
        key: str,
        max_requests: int,
        per_seconds: float = 1.0,
        redis_url: str | None = None,
    ) -> None:
        self.redis_key = f"ratelimit:{key}"
        # Seconds between allowed requests at the target rate -- e.g.
        # max_requests=10, per_seconds=1.0 -> one request every 100ms.
        self.emission_interval = per_seconds / max_requests
        self.redis_url = redis_url or settings.REDIS_URL

    async def acquire(self) -> None:
        global _warned_fallback
        try:
            script = await _get_script(self.redis_url)
            wait_ms = await script(
                keys=[self.redis_key],
                args=[self.emission_interval, time.time()],
            )
            wait_s = int(wait_ms) / 1000.0
            if wait_s > 0:
                await asyncio.sleep(wait_s)
        except Exception as exc:  # noqa: BLE001 - fail open, never block ingestion on Redis
            if not _warned_fallback:
                logger.warning(
                    "RedisRateLimiter: Redis unavailable (%s) -- proceeding "
                    "unthrottled for %s. Further occurrences logged at debug.",
                    exc, self.redis_key,
                )
                _warned_fallback = True
            else:
                logger.debug("RedisRateLimiter: Redis unavailable for %s: %s", self.redis_key, exc)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *exc):
        pass
