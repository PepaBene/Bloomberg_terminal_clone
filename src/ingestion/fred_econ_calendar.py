"""FRED economic-release calendar connector.

Populates :class:`~src.models.economic_calendar.EconomicRelease` from the FRED
*releases* API.  For a curated set of high-signal US economic releases we pull
the schedule of release dates (``fred/release/dates``, including future
scheduled dates) and store one row per (release_type, release_date).

Honesty note
------------
FRED publishes the release *schedule* only — it does not provide the
consensus / prior / actual data points, surprise magnitudes, release times, or
period labels that a full economic calendar would carry.  Those columns
(``consensus_value``, ``prior_value``, ``actual_value``, ``surprise_value``,
``surprise_magnitude``, ``release_time``, ``period_label`` and the impact /
AI-analysis columns) are therefore left NULL — we populate only what FRED
honestly supplies: the release identity, category, date, country, importance
and source.
"""

import logging
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# Curated FRED releases -> (release_type, release_category, importance).
# release_id : (type_code, category, importance)
#   category is one of ECONOMIC_DATA / CENTRAL_BANK (per the model's convention).
CURATED_RELEASES: dict[int, tuple[str, str, str]] = {
    10: ("CPI", "ECONOMIC_DATA", "HIGH"),               # Consumer Price Index
    46: ("PPI", "ECONOMIC_DATA", "MEDIUM"),             # Producer Price Index
    50: ("NFP", "ECONOMIC_DATA", "HIGH"),               # Employment Situation
    53: ("GDP", "ECONOMIC_DATA", "HIGH"),               # Gross Domestic Product
    54: ("PCE", "ECONOMIC_DATA", "HIGH"),               # Personal Income & Outlays
    9: ("RETAIL_SALES", "ECONOMIC_DATA", "HIGH"),       # Advance Retail Sales
    13: ("INDUSTRIAL_PRODUCTION", "ECONOMIC_DATA", "MEDIUM"),  # G.17 IP & Cap Util
    27: ("HOUSING_STARTS", "ECONOMIC_DATA", "MEDIUM"),  # New Residential Construction
    51: ("TRADE_BALANCE", "ECONOMIC_DATA", "MEDIUM"),   # US International Trade
    180: ("JOBLESS_CLAIMS", "ECONOMIC_DATA", "MEDIUM"), # UI Weekly Claims
    192: ("JOLTS", "ECONOMIC_DATA", "MEDIUM"),          # Job Openings (JOLTS)
    18: ("INTEREST_RATES", "CENTRAL_BANK", "MEDIUM"),   # H.15 Selected Interest Rates
}


class FredEconCalendarConnector(BaseConnector):
    """Ingest scheduled US economic releases from FRED."""

    name = "FRED Economic Calendar"
    connector_type = "BATCH_API"
    data_domain = "ECONOMIC_CALENDAR"

    def __init__(
        self,
        api_key: str | None = None,
        lookback_days: int = 90,
        lookahead_days: int = 180,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.lookback_days = lookback_days
        self.lookahead_days = lookahead_days
        rate_limit = getattr(settings, "FRED_RATE_LIMIT", 120)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fred_get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        all_params = {"api_key": self.api_key, "file_type": "json"}
        if params:
            all_params.update(params)
        resp = await client.get(f"{FRED_BASE_URL}/{path}", params=all_params)
        resp.raise_for_status()
        return resp.json()

    async def extract(self) -> list[dict[str, Any]]:
        """Pull scheduled release dates for each curated release."""
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping economic calendar extraction")
            return []

        today = date.today()
        window_start = today - timedelta(days=self.lookback_days)
        window_end = today + timedelta(days=self.lookahead_days)

        records: list[dict[str, Any]] = []
        for release_id, (rtype, category, importance) in CURATED_RELEASES.items():
            try:
                data = await self._fred_get(
                    "release/dates",
                    params={
                        "release_id": release_id,
                        # include future scheduled dates that have no data yet
                        "include_release_dates_with_no_data": "true",
                        "sort_order": "desc",
                        "limit": 60,
                    },
                )
                dates = data.get("release_dates", [])
                kept = 0
                for entry in dates:
                    raw_date = entry.get("date")
                    if not raw_date:
                        continue
                    try:
                        rel_date = date.fromisoformat(raw_date)
                    except ValueError:
                        continue
                    if not (window_start <= rel_date <= window_end):
                        continue
                    records.append(
                        {
                            "release_type": rtype,
                            "release_category": category,
                            "release_date": rel_date,
                            "importance": importance,
                            "country_code": "US",
                            "source": "FRED",
                        }
                    )
                    kept += 1
                logger.info(
                    "  FRED release %s (%s): %d dates in window", release_id, rtype, kept
                )
            except Exception as e:  # noqa: BLE001
                logger.error("  FRED release %s: failed: %s", release_id, e)

        logger.info("  FRED econ calendar: assembled %d release rows", len(records))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for rec in records:
            if not rec.get("release_type") or not rec.get("release_date"):
                continue
            if not rec.get("release_category"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Idempotently upsert on (release_type, release_date, source)."""
        from src.models.economic_calendar import EconomicRelease

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for rec in records:
            try:
                existing = await session.execute(
                    select(EconomicRelease).where(
                        EconomicRelease.release_type == rec["release_type"],
                        EconomicRelease.release_date == rec["release_date"],
                        EconomicRelease.source == "FRED",
                    )
                )
                row = existing.scalar_one_or_none()
                if row is None:
                    row = EconomicRelease(
                        release_type=rec["release_type"],
                        release_category=rec["release_category"],
                        release_date=rec["release_date"],
                        importance=rec.get("importance"),
                        country_code=rec.get("country_code", "US"),
                        source="FRED",
                        ai_enabled=False,
                    )
                    session.add(row)
                    stats["inserted"] += 1
                else:
                    row.release_category = rec["release_category"]
                    row.importance = rec.get("importance")
                    row.country_code = rec.get("country_code", "US")
                    stats["updated"] += 1
                await session.flush()
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "  Failed to load release %s %s: %s",
                    rec.get("release_type"),
                    rec.get("release_date"),
                    e,
                )
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
