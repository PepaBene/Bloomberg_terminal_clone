"""FRED commodity price connector.

Populates :class:`~src.models.commodity_intelligence.CommodityProfile` (one
reference row per tracked commodity) and
:class:`~src.models.commodity_intelligence.CommodityPrice` (daily/weekly/monthly
price series) from a curated set of FRED commodity price series.

Honesty note
------------
FRED publishes a single spot/benchmark *price* per date, not full OHLCV.  We
store that value in ``close_price`` and leave ``open_price``, ``high_price``,
``low_price`` and ``volume`` NULL.  The ``CommodityProfile`` model has no
dedicated ``fred_series_code`` column, so the FRED series id lives only in this
connector's ``COMMODITIES`` map (the profile keeps the friendly
``commodity_code``); ``primary_source`` is set to ``FRED``.

FRED no longer carries a clean spot gold or silver price series (the LBMA
AM/PM fixings were discontinued and only volatility / PPI / import-export index
series remain), so precious metals are intentionally omitted rather than
stored as a misleading proxy.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class CommoditySpec:
    code: str          # friendly commodity_code stored in the DB
    name: str
    category: str      # ENERGY / METALS / AGRICULTURE
    unit: str
    fred_series: str   # source FRED series id


# Curated, verified-live FRED commodity price series.
COMMODITIES: list[CommoditySpec] = [
    # Energy
    CommoditySpec("WTI", "Crude Oil (WTI)", "ENERGY", "USD per Barrel", "DCOILWTICO"),
    CommoditySpec("BRENT", "Crude Oil (Brent)", "ENERGY", "USD per Barrel", "DCOILBRENTEU"),
    CommoditySpec("NATGAS", "Natural Gas (Henry Hub)", "ENERGY", "USD per Million BTU", "DHHNGSP"),
    CommoditySpec("GASOLINE", "Gasoline (US Regular)", "ENERGY", "USD per Gallon", "GASREGW"),
    # Metals
    CommoditySpec("COPPER", "Copper", "METALS", "USD per Metric Ton", "PCOPPUSDM"),
    CommoditySpec("ALUMINUM", "Aluminum", "METALS", "USD per Metric Ton", "PALUMUSDM"),
    CommoditySpec("IRON_ORE", "Iron Ore", "METALS", "USD per Metric Ton", "PIORECRUSDM"),
    # Agriculture
    CommoditySpec("WHEAT", "Wheat", "AGRICULTURE", "USD per Metric Ton", "PWHEAMTUSDM"),
    CommoditySpec("CORN", "Corn", "AGRICULTURE", "USD per Metric Ton", "PMAIZMTUSDM"),
    CommoditySpec("SOYBEANS", "Soybeans", "AGRICULTURE", "USD per Metric Ton", "PSOYBUSDM"),
]


class FredCommoditiesConnector(BaseConnector):
    """Ingest curated commodity spot/benchmark prices from FRED."""

    name = "FRED Commodities"
    connector_type = "BATCH_API"
    data_domain = "COMMODITIES"

    def __init__(
        self,
        api_key: str | None = None,
        lookback_days: int = 90,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.lookback_days = lookback_days
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
        """Pull recent observations for each curated commodity series."""
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping commodities extraction")
            return []

        start = (date.today() - timedelta(days=self.lookback_days)).isoformat()

        # Always emit profile rows so the reference table stays populated even if
        # a given series has no fresh observation in the window.
        records: list[dict[str, Any]] = [
            {"kind": "profile", "spec": spec} for spec in COMMODITIES
        ]

        for spec in COMMODITIES:
            try:
                data = await self._fred_get(
                    "series/observations",
                    params={
                        "series_id": spec.fred_series,
                        "observation_start": start,
                        "sort_order": "asc",
                    },
                )
                obs = data.get("observations", [])
                kept = 0
                for o in obs:
                    raw = o.get("value")
                    raw_date = o.get("date")
                    if not raw_date or raw is None or raw == ".":
                        continue
                    try:
                        price = Decimal(raw)
                    except (InvalidOperation, ValueError):
                        continue
                    try:
                        price_date = date.fromisoformat(raw_date)
                    except ValueError:
                        continue
                    records.append(
                        {
                            "kind": "price",
                            "commodity_code": spec.code,
                            "price_date": price_date,
                            "close_price": price,
                        }
                    )
                    kept += 1
                logger.info(
                    "  FRED commodity %s (%s): %d observations",
                    spec.fred_series,
                    spec.code,
                    kept,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("  FRED commodity %s: failed: %s", spec.fred_series, e)

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for rec in records:
            if rec["kind"] == "profile":
                valid.append(rec)
            elif rec.get("commodity_code") and rec.get("price_date") and rec.get("close_price") is not None:
                valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Idempotently upsert profiles (by commodity_code) and prices
        (by commodity_code + price_date)."""
        from src.models.commodity_intelligence import CommodityPrice, CommodityProfile

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                if rec["kind"] == "profile":
                    spec: CommoditySpec = rec["spec"]
                    existing = await session.execute(
                        select(CommodityProfile).where(
                            CommodityProfile.commodity_code == spec.code
                        )
                    )
                    prof = existing.scalar_one_or_none()
                    if prof is None:
                        prof = CommodityProfile(
                            commodity_code=spec.code,
                            commodity_name=spec.name,
                            category=spec.category,
                            unit=spec.unit,
                            primary_source="FRED",
                        )
                        session.add(prof)
                        stats["inserted"] += 1
                    else:
                        prof.commodity_name = spec.name
                        prof.category = spec.category
                        prof.unit = spec.unit
                        prof.primary_source = "FRED"
                        stats["updated"] += 1
                else:
                    existing = await session.execute(
                        select(CommodityPrice).where(
                            CommodityPrice.commodity_code == rec["commodity_code"],
                            CommodityPrice.price_date == rec["price_date"],
                        )
                    )
                    price = existing.scalar_one_or_none()
                    if price is None:
                        price = CommodityPrice(
                            commodity_code=rec["commodity_code"],
                            price_date=rec["price_date"],
                            close_price=rec["close_price"],
                            source="FRED",
                        )
                        session.add(price)
                        stats["inserted"] += 1
                    else:
                        price.close_price = rec["close_price"]
                        price.source = "FRED"
                        stats["updated"] += 1
                await session.flush()
            except Exception as e:  # noqa: BLE001
                logger.error("  Failed to load commodity record %s: %s", rec, e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
