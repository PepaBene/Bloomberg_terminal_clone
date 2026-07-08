"""D11 FI Supplement: FRED credit spread indices ingestion connector.

Fetches BofA/ICE OAS and effective-yield indices from FRED and writes
``CreditSpreadIndex`` rows, plus optional ``CreditSpreadPercentile``
statistics. Auth / rate-limit / HTTP handling mirrors ``fred_macro.py``.
"""

import logging
import statistics
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

# BofA ICE indices available via FRED (series_id -> descriptive name).
FRED_SPREAD_SERIES = {
    "BAMLC0A0CM": "ICE BofA US Corporate Master OAS",
    "BAMLC0A1CAAA": "ICE BofA US Corporate AAA OAS",
    "BAMLC0A2CAA": "ICE BofA US Corporate AA OAS",
    "BAMLC0A3CA": "ICE BofA US Corporate A OAS",
    "BAMLC0A4CBBB": "ICE BofA US Corporate BBB OAS",
    "BAMLH0A0HYM2": "ICE BofA US High Yield Master OAS",
    "BAMLH0A1HYBB": "ICE BofA US High Yield BB OAS",
    "BAMLH0A2HYB": "ICE BofA US High Yield B OAS",
    "BAMLH0A3HYC": "ICE BofA US High Yield CCC & Lower OAS",
    "BAMLC0A0CMEY": "ICE BofA US Corporate Effective Yield",
    "BAMLH0A0HYM2EY": "ICE BofA US High Yield Effective Yield",
}

# Rating bucket per series (best-effort classification for querying/filtering).
_RATING_CATEGORY = {
    "BAMLC0A0CM": "IG",
    "BAMLC0A1CAAA": "AAA",
    "BAMLC0A2CAA": "AA",
    "BAMLC0A3CA": "A",
    "BAMLC0A4CBBB": "BBB",
    "BAMLH0A0HYM2": "HY",
    "BAMLH0A1HYBB": "BB",
    "BAMLH0A2HYB": "B",
    "BAMLH0A3HYC": "CCC",
    "BAMLC0A0CMEY": "IG",
    "BAMLH0A0HYM2EY": "HY",
}


def rating_category(series_id: str) -> str | None:
    return _RATING_CATEGORY.get(series_id)


class FREDCreditSpreadsConnector(BaseConnector):
    """Ingest credit spread indices from FRED.

    FRED OAS series are published in percent (e.g. ``1.23`` = 123 bps); this
    connector stores ``spread_bps`` in basis points (value x 100).
    """

    name = "FRED Credit Spreads"
    connector_type = "BATCH_API"
    data_domain = "CREDIT_SPREADS"

    def __init__(
        self,
        api_key: str | None = None,
        series_ids: list[str] | None = None,
        start_date: str | None = None,
        compute_percentiles: bool = True,
        lookback_years: int = 5,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.series_ids = series_ids or list(FRED_SPREAD_SERIES.keys())
        self.start_date = start_date  # e.g. "2010-01-01"
        self.compute_percentiles = compute_percentiles
        self.lookback_years = lookback_years
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
        """Pull observations for each configured FRED spread series."""
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping credit-spread extraction")
            return []

        records: list[dict[str, Any]] = []
        for series_id in self.series_ids:
            try:
                obs_params: dict[str, Any] = {"series_id": series_id}
                if self.start_date:
                    obs_params["observation_start"] = self.start_date
                obs_data = await self._fred_get(
                    "series/observations", params=obs_params
                )
                observations = obs_data.get("observations", [])
                records.append({
                    "series_id": series_id,
                    "observations": observations,
                })
                logger.info(
                    "  FRED spreads: %s — %d observations",
                    series_id, len(observations),
                )
            except Exception as e:  # noqa: BLE001
                logger.error("  FRED spreads: failed to fetch %s: %s", series_id, e)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop missing-value observations ('.' sentinel used by FRED)."""
        valid = []
        for rec in records:
            if not rec.get("series_id"):
                continue
            clean = [
                obs for obs in rec.get("observations", [])
                if obs.get("value") and obs["value"] != "."
            ]
            rec["observations"] = clean
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build CreditSpreadIndex rows (+ percentile stats) per series."""
        transformed = []
        for rec in records:
            series_id = rec["series_id"]
            index_name = FRED_SPREAD_SERIES.get(series_id, series_id)
            rows = []
            numeric_points: list[tuple[date, float]] = []
            for obs in rec.get("observations", []):
                try:
                    obs_date = date.fromisoformat(obs["date"])
                    pct = float(obs["value"])
                except (KeyError, ValueError):
                    continue
                spread_bps = round(pct * 100.0, 4)
                numeric_points.append((obs_date, spread_bps))
                rows.append({
                    "series_id": series_id,
                    "observation_date": obs_date,
                    "index_name": index_name,
                    "rating_category": rating_category(series_id),
                    "spread_bps": spread_bps,
                    "source": "FRED",
                })

            percentile = None
            if self.compute_percentiles and numeric_points:
                percentile = self._compute_percentile(series_id, numeric_points)

            transformed.append({
                "series_id": series_id,
                "rows": rows,
                "percentile": percentile,
            })
        return transformed

    def _compute_percentile(
        self, series_id: str, points: list[tuple[date, float]]
    ) -> dict[str, Any] | None:
        """Compute where the latest OAS sits within its lookback window."""
        points = sorted(points, key=lambda p: p[0])
        as_of, current = points[-1]
        cutoff = date(as_of.year - self.lookback_years, as_of.month, as_of.day)
        window = [v for d, v in points if d >= cutoff]
        if len(window) < 2:
            return None
        below = sum(1 for v in window if v <= current)
        pct_rank = round(100.0 * below / len(window), 2)
        mean_v = statistics.fmean(window)
        std_v = statistics.pstdev(window)
        z = round((current - mean_v) / std_v, 4) if std_v else None
        return {
            "series_id": series_id,
            "as_of_date": as_of,
            "lookback_years": self.lookback_years,
            "percentile_rank": pct_rank,
            "current_oas": current,
            "min_oas": min(window),
            "max_oas": max(window),
            "mean_oas": round(mean_v, 4),
            "std_dev": round(std_v, 4),
            "z_score": z,
        }

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write CreditSpreadIndex + CreditSpreadPercentile rows."""
        from src.models.credit_spread import CreditSpreadIndex, CreditSpreadPercentile

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            series_id = rec["series_id"]
            for row in rec.get("rows", []):
                try:
                    existing = await session.execute(
                        select(CreditSpreadIndex).where(
                            CreditSpreadIndex.series_id == series_id,
                            CreditSpreadIndex.observation_date == row["observation_date"],
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        stats["skipped"] += 1
                        continue
                    session.add(CreditSpreadIndex(
                        series_id=series_id,
                        observation_date=row["observation_date"],
                        index_name=row.get("index_name"),
                        rating_category=row.get("rating_category"),
                        spread_bps=Decimal(str(row["spread_bps"])),
                        source=row.get("source", "FRED"),
                    ))
                    stats["inserted"] += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("Error loading spread row (%s): %s", series_id, e)
                    stats["errors"] += 1

            pct = rec.get("percentile")
            if pct:
                try:
                    existing_p = await session.execute(
                        select(CreditSpreadPercentile).where(
                            CreditSpreadPercentile.series_id == series_id,
                            CreditSpreadPercentile.as_of_date == pct["as_of_date"],
                            CreditSpreadPercentile.lookback_years == pct["lookback_years"],
                        )
                    )
                    if existing_p.scalar_one_or_none() is None:
                        session.add(CreditSpreadPercentile(
                            series_id=series_id,
                            as_of_date=pct["as_of_date"],
                            lookback_years=pct["lookback_years"],
                            percentile_rank=Decimal(str(pct["percentile_rank"])),
                            current_oas=Decimal(str(pct["current_oas"])),
                            min_oas=Decimal(str(pct["min_oas"])),
                            max_oas=Decimal(str(pct["max_oas"])),
                            mean_oas=Decimal(str(pct["mean_oas"])),
                            std_dev=Decimal(str(pct["std_dev"])),
                            z_score=Decimal(str(pct["z_score"])) if pct.get("z_score") is not None else None,
                        ))
                        stats["inserted"] += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("Error loading percentile (%s): %s", series_id, e)
                    stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
