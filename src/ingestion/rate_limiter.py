"""Async-safe rate limiter for external API calls."""

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter for async contexts."""

    def __init__(self, max_requests: int, per_seconds: float = 1.0):
        self.max_requests = max_requests
        self.per_seconds = per_seconds
        self._tokens = float(max_requests)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time. Must be called under lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.max_requests,
            self._tokens + elapsed * (self.max_requests / self.per_seconds),
        )
        self._last_refill = now

    @property
    def _rate(self) -> float:
        """Tokens per second."""
        return self.max_requests / self.per_seconds

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_time = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait_time)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *exc):
        pass
