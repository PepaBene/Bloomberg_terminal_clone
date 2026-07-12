"""Money Market Rate ingestion from FRED (Part 2).

FRED series: SOFR, DFF, DFEDTAR, DTB3, DTB6, DTB1YR, DCPF3M, DCPN3M, DPRIME.

Auth / rate-limit / HTTP handling mirrors ``fred_credit_spreads.py`` (same
FRED_API_KEY, same ``series/observations`` endpoint, same "." missing-value
sentinel handling) — this connector was previously a stub whose ``extract()``
always returned ``[]``; ``money_market_rates`` had a real ``load()`` and a
real API reader (``GET /v1/macro/money-markets``) but nothing ever populated
the table.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# FRED series → internal rate_type mapping
FRED_SERIES_MAP = {
    "SOFR": "SOFR",
    "DFF": "FED_FUNDS_EFFECTIVE",
    "DFEDTAR": "FED_FUNDS_TARGET",
    "DTB3": "TBILL_3M",
    "DTB6": "TBILL_6M",
    "DTB1YR": "TBILL_1Y",
    "DCPF3M": "COMMERCIAL_PAPER_FIN",
    "DCPN3M": "COMMERCIAL_PAPER_NONFIN",
    "DPRIME": "PRIME",
}


class FredMoneyMarketConnector(BaseConnector):
    """Fetch money market rates from FRED API."""

    name = "FRED Money Market Rates"
    connector_type = "BATCH_API"
    data_domain = "MONEY_MARKET"

    def __init__(
        self,
        api_key: str | None = None,
        series_map: dict[str, str] | None = None,
        start_date: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.series_map = series_map or dict(FRED_SERIES_MAP)
        self.start_date = start_date
        rate_limit = getattr(settings, "FRED_RATE_LIMIT", 120)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fred_get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Make a rate-limited GET request to FRED API."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        all_params = {"api_key": self.api_key, "file_type": "json"}
        if params:
            all_params.update(params)
        resp = await client.get(f"{FRED_BASE_URL}/{path}", params=all_params)
        resp.raise_for_status()
        return resp.json()

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch money market rate observations from FRED for each series."""
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping money market extraction")
            return []

        records: list[dict[str, Any]] = []
        for series_id, rate_type in self.series_map.items():
            try:
                obs_params: dict[str, Any] = {"series_id": series_id}
                if self.start_date:
                    obs_params["observation_start"] = self.start_date
                obs_data = await self._fred_get("series/observations", params=obs_params)
                observations = obs_data.get("observations", [])
                for obs in observations:
                    records.append({
                        "series_id": series_id,
                        "rate_type": rate_type,
                        "rate_date": obs.get("date"),
                        "rate_value": obs.get("value"),
                    })
                logger.info(
                    "  FRED money market: %s (%s) — %d observations",
                    series_id, rate_type, len(observations),
                )
            except httpx.HTTPStatusError as e:
                logger.error("  FRED money market: failed to fetch %s: %s", series_id, e)
            except Exception as e:  # noqa: BLE001
                logger.error("  FRED money market: unexpected error for %s: %s", series_id, e)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate money market rate records — drop FRED's '.' missing-value sentinel."""
        valid = []
        for rec in records:
            if not rec.get("rate_date") or not rec.get("rate_type"):
                continue
            value = rec.get("rate_value")
            if value is None or value == ".":
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform FRED series observations to internal format.

        FRED publishes these series in percent (e.g. ``5.33`` = 5.33%);
        ``MoneyMarketRate.rate_value`` stores the decimal fraction (0.0533).
        """
        transformed = []
        for rec in records:
            try:
                rate_date = date.fromisoformat(rec["rate_date"])
            except (ValueError, TypeError):
                continue
            pct = float(rec["rate_value"])
            transformed.append({
                "rate_date": rate_date,
                "rate_type": rec["rate_type"],
                "rate_value": round(pct / 100.0, 6),
                "source": "FRED",
            })
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load money market rates, de-duping on (rate_date, rate_type)."""
        from src.models.fed_meeting import MoneyMarketRate

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for rec in records:
            try:
                existing = await session.execute(
                    select(MoneyMarketRate).where(
                        MoneyMarketRate.rate_date == rec["rate_date"],
                        MoneyMarketRate.rate_type == rec["rate_type"],
                    )
                )
                row = existing.scalar_one_or_none()
                if row is not None:
                    row.rate_value = Decimal(str(rec["rate_value"]))
                    row.source = rec.get("source", "FRED")
                    stats["updated"] += 1
                    continue

                rate = MoneyMarketRate(
                    rate_date=rec["rate_date"],
                    rate_type=rec["rate_type"],
                    rate_value=Decimal(str(rec["rate_value"])),
                    source=rec.get("source", "FRED"),
                )
                session.add(rate)
                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading money market rate: %s", e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
