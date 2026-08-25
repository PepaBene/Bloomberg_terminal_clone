"""FRED API connector for macroeconomic data ingestion (Spec 9.6)."""

import logging
from datetime import date, datetime, timezone
from typing import Any
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# 15 core US macro series to seed
FRED_SEED_SERIES = [
    # GDP
    {"series_id": "GDP", "category": "GDP", "name": "Gross Domestic Product", "unit": "Billions of Dollars", "frequency": "QUARTERLY", "sa": "SAAR"},
    {"series_id": "GDPC1", "category": "GDP", "name": "Real Gross Domestic Product", "unit": "Billions of Chained 2017 Dollars", "frequency": "QUARTERLY", "sa": "SAAR"},
    # Labor
    {"series_id": "UNRATE", "category": "LABOR", "name": "Unemployment Rate", "unit": "Percent", "frequency": "MONTHLY", "sa": "SA"},
    {"series_id": "PAYEMS", "category": "LABOR", "name": "Total Nonfarm Payrolls", "unit": "Thousands of Persons", "frequency": "MONTHLY", "sa": "SA"},
    # Prices
    {"series_id": "CPIAUCSL", "category": "PRICES", "name": "Consumer Price Index for All Urban Consumers", "unit": "Index 1982-84=100", "frequency": "MONTHLY", "sa": "SA"},
    {"series_id": "CPILFESL", "category": "PRICES", "name": "CPI Less Food and Energy (Core CPI)", "unit": "Index 1982-84=100", "frequency": "MONTHLY", "sa": "SA"},
    {"series_id": "PCEPI", "category": "PRICES", "name": "PCE Price Index", "unit": "Index 2017=100", "frequency": "MONTHLY", "sa": "SA"},
    # Rates
    {"series_id": "FEDFUNDS", "category": "RATES", "name": "Federal Funds Effective Rate", "unit": "Percent", "frequency": "MONTHLY", "sa": "NSA"},
    {"series_id": "DGS10", "category": "RATES", "name": "10-Year Treasury Constant Maturity Rate", "unit": "Percent", "frequency": "DAILY", "sa": "NSA"},
    {"series_id": "DGS2", "category": "RATES", "name": "2-Year Treasury Constant Maturity Rate", "unit": "Percent", "frequency": "DAILY", "sa": "NSA"},
    {"series_id": "T10Y2Y", "category": "RATES", "name": "10-Year Minus 2-Year Treasury Spread", "unit": "Percent", "frequency": "DAILY", "sa": "NSA"},
    {"series_id": "VIXCLS", "category": "RATES", "name": "CBOE Volatility Index (VIX)", "unit": "Index", "frequency": "DAILY", "sa": "NSA"},
    # Housing
    {"series_id": "HOUST", "category": "HOUSING", "name": "Housing Starts: Total", "unit": "Thousands of Units", "frequency": "MONTHLY", "sa": "SAAR"},
    # Consumer
    {"series_id": "RSAFS", "category": "CONSUMER", "name": "Advance Retail Sales: Total", "unit": "Millions of Dollars", "frequency": "MONTHLY", "sa": "SA"},
    # Manufacturing
    {"series_id": "INDPRO", "category": "MANUFACTURING", "name": "Industrial Production Index", "unit": "Index 2017=100", "frequency": "MONTHLY", "sa": "SA"},
    {"series_id": "UMCSENT", "category": "CONSUMER", "name": "University of Michigan: Consumer Sentiment", "unit": "Index 1966:Q1=100", "frequency": "MONTHLY", "sa": "NSA"},
]

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


class FredMacroConnector(BaseConnector):
    """Ingest macroeconomic data from the FRED API."""

    name = "FRED Macro"
    connector_type = "BATCH_API"
    data_domain = "MACRO"

    def __init__(
        self,
        api_key: str | None = None,
        series_ids: list[str] | None = None,
        start_date: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.series_ids = series_ids or [s["series_id"] for s in FRED_SEED_SERIES]
        self.start_date = start_date  # e.g. "2000-01-01"
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
        """Pull series metadata + observations from FRED."""
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping extraction")
            return []

        records: list[dict[str, Any]] = []
        seed_lookup = {s["series_id"]: s for s in FRED_SEED_SERIES}

        for series_id in self.series_ids:
            try:
                # Fetch series info
                info = await self._fred_get(
                    "series", params={"series_id": series_id}
                )
                series_meta = info.get("seriess", [{}])[0]

                # Fetch observations
                obs_params: dict[str, Any] = {"series_id": series_id}
                if self.start_date:
                    obs_params["observation_start"] = self.start_date
                obs_data = await self._fred_get("series/observations", params=obs_params)
                observations = obs_data.get("observations", [])

                seed = seed_lookup.get(series_id, {})
                records.append({
                    "series_id": series_id,
                    "meta": series_meta,
                    "seed": seed,
                    "observations": observations,
                })
                logger.info(f"  FRED: {series_id} — {len(observations)} observations")

            except Exception as e:
                logger.error(f"  FRED: Failed to fetch {series_id}: {e}")

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate FRED records — filter out entries with missing data."""
        valid = []
        for rec in records:
            if not rec.get("series_id"):
                continue
            # Filter out observations with missing values
            clean_obs = [
                obs for obs in rec.get("observations", [])
                if obs.get("value") and obs["value"] != "."
            ]
            rec["observations"] = clean_obs
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform FRED data into our internal format."""
        transformed = []
        for rec in records:
            meta = rec.get("meta", {})
            seed = rec.get("seed", {})

            indicator = {
                "indicator_code": rec["series_id"],
                "name": meta.get("title", seed.get("name", rec["series_id"])),
                "short_name": rec["series_id"],
                "description": meta.get("notes", ""),
                "category": seed.get("category", "OTHER"),
                "country_code": "US",
                "frequency": seed.get("frequency", meta.get("frequency_short", "MONTHLY")).upper(),
                "unit": seed.get("unit", meta.get("units", "")),
                "seasonal_adjustment": seed.get("sa", meta.get("seasonal_adjustment_short", "NSA")),
                "source_agency": "Federal Reserve Economic Data (FRED)",
                "source_url": f"https://fred.stlouisfed.org/series/{rec['series_id']}",
                "source_series_id": rec["series_id"],
                "is_active": True,
            }

            values = []
            for obs in rec.get("observations", []):
                try:
                    values.append({
                        "observation_date": obs["date"],
                        "value": obs["value"],
                        "release_date": obs.get("realtime_start"),
                        "vintage_date": obs.get("realtime_start", obs["date"]),
                    })
                except (KeyError, ValueError):
                    continue

            transformed.append({
                "indicator": indicator,
                "values": values,
            })
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write macro indicators and values to database."""
        from src.models.macro import MacroIndicator, MacroValue

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                ind_data = rec["indicator"]

                # Upsert indicator
                result = await session.execute(
                    select(MacroIndicator).where(
                        MacroIndicator.indicator_code == ind_data["indicator_code"]
                    )
                )
                indicator = result.scalar_one_or_none()

                if indicator is None:
                    import uuid as _uuid
                    indicator = MacroIndicator(
                        indicator_id=_uuid.uuid4(),
                        **ind_data,
                    )
                    session.add(indicator)
                    await session.flush()
                    stats["inserted"] += 1
                else:
                    # Update fields
                    for key, val in ind_data.items():
                        if val is not None:
                            setattr(indicator, key, val)
                    stats["updated"] += 1

                # Load values
                for val_data in rec.get("values", []):
                    try:
                        obs_date = date.fromisoformat(val_data["observation_date"])
                        vintage = date.fromisoformat(val_data.get("vintage_date", val_data["observation_date"]))

                        # Check if exists
                        existing = await session.execute(
                            select(MacroValue).where(
                                MacroValue.indicator_id == indicator.indicator_id,
                                MacroValue.observation_date == obs_date,
                                MacroValue.vintage_date == vintage,
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            stats["skipped"] += 1
                            continue

                        value = MacroValue(
                            indicator_id=indicator.indicator_id,
                            observation_date=obs_date,
                            vintage_date=vintage,
                            value=Decimal(val_data["value"]),
                            release_date=date.fromisoformat(val_data["release_date"]) if val_data.get("release_date") else None,
                            source="FRED",
                        )
                        session.add(value)
                        stats["inserted"] += 1
                    except Exception as e:
                        logger.debug(f"    Skip value: {e}")
                        stats["errors"] += 1

                await session.flush()

            except Exception as e:
                logger.error(f"  Failed to load indicator: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
