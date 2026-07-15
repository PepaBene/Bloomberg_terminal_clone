"""EIA (US Energy Information Administration) commodity stock/inventory connector.

Provides the real supply-side data underlying
``GET /global/commodities/{code}/supply-demand``
(``src/api/routers/global_intelligence.py``), which previously had no actual
supply/demand data source at all and inferred a "signal" purely from price
deviation from its own 30-day average (an explicit ``# PLACEHOLDER`` in the
code, not a real supply/demand measurement).

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Outbound network access is blocked in this sandbox, so this connector has
never been exercised against a live EIA response. It is written against
EIA's documented API v2 ``/v2/seriesid/{series_id}`` compatibility endpoint
(a v1-series-ID shim EIA ships specifically so v1 series IDs keep working
without callers needing to learn the v2 route/facet query structure), using
well-known, long-stable EIA v1 series IDs for weekly petroleum/natural-gas
stock reports:

    PET.WCESTUS1.W  — Weekly US Ending Stocks excluding SPR of Crude Oil
                       (Thousand Barrels)
    PET.WGTSTUS1.W  — Weekly US Ending Stocks of Total Gasoline
                       (Thousand Barrels)
    NG.NW2_EPG0_SWO_R48_BCF.W — Weekly Lower 48 States Natural Gas Working
                       Underground Storage (Billion Cubic Feet)

The expected response envelope (``{"response": {"data": [{"period":...,
"value":...,"units":...}, ...]}}``) is EIA's documented v2 shape, not
confirmed against a live payload here. Validate against a real API key and
response before relying on this in production.

Coverage is intentionally partial and honest about it: EIA tracks *US*
physical stock levels, so only commodities with a genuine US-stocks concept
are mapped (WTI crude, US gasoline, US natural gas storage). BRENT is an
international/UK benchmark with no corresponding EIA US-stocks series and is
deliberately left unmapped rather than forced onto a mismatched series —
metals and agricultural commodities have no EIA coverage at all (their real
free sources would be LME/COMEX warehouse data and USDA NASS Quick Stats
respectively, neither of which is wired up here; see
``CONNECTING_TO_REAL_DATA.md``). The API route/router honestly reports which
commodities have real inventory-based signal vs. which fall back to the
price-heuristic proxy (see ``get_commodity_supply_demand`` in
``global_intelligence.py``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.commodity_intelligence import CommodityInventory

logger = logging.getLogger(__name__)

EIA_BASE_URL = "https://api.eia.gov/v2"


@dataclass(frozen=True)
class EiaSeriesSpec:
    commodity_code: str   # matches CommodityProfile.commodity_code (fred_commodities.py)
    series_id: str        # EIA v1-compatible series id
    metric_name: str
    unit: str


# US-stocks-only coverage — see module docstring for why BRENT/metals/ag are
# deliberately excluded rather than mapped to a mismatched series.
EIA_SERIES: list[EiaSeriesSpec] = [
    EiaSeriesSpec(
        "WTI", "PET.WCESTUS1.W",
        "US Commercial Crude Oil Stocks (excl. SPR)", "Thousand Barrels",
    ),
    EiaSeriesSpec(
        "GASOLINE", "PET.WGTSTUS1.W",
        "US Total Gasoline Stocks", "Thousand Barrels",
    ),
    EiaSeriesSpec(
        "NATGAS", "NG.NW2_EPG0_SWO_R48_BCF.W",
        "Lower-48 Natural Gas Working Underground Storage", "Billion Cubic Feet",
    ),
]


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def parse_eia_response(spec: EiaSeriesSpec, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure: map one EIA ``/v2/seriesid/{id}`` JSON payload to raw stock rows.

    Expected shape (EIA API v2 documented envelope):
        {"response": {"data": [{"period": "2024-05-03", "value": 123456,
                                 "units": "MBBL", ...}, ...]}}
    Rows missing a parseable period or value are dropped, not fabricated.
    """
    rows = ((payload or {}).get("response") or {}).get("data") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        as_of_date = _parse_date(row.get("period"))
        stock_level = _parse_decimal(row.get("value"))
        if as_of_date is None or stock_level is None:
            continue
        out.append(
            {
                "commodity_code": spec.commodity_code,
                "as_of_date": as_of_date,
                "stock_level": stock_level,
                "stock_unit": row.get("units") or spec.unit,
                "metric_name": spec.metric_name,
                "source": "EIA",
            }
        )
    return out


class EIACommodityInventoryConnector(BaseConnector):
    """Ingest weekly US petroleum/natural-gas stock levels from EIA."""

    name = "EIA Commodity Inventory"
    connector_type = "BATCH_API"
    data_domain = "COMMODITIES"

    def __init__(
        self,
        api_key: str | None = None,
        lookback_periods: int = 52,
    ):
        self.api_key = api_key or getattr(settings, "EIA_API_KEY", "")
        self.lookback_periods = lookback_periods
        self.rate_limiter = RateLimiter(
            max_requests=getattr(settings, "EIA_RATE_LIMIT", 30), per_seconds=60.0
        )

    async def extract(self) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning(
                "[%s] no EIA_API_KEY configured — skipping extraction "
                "(register free at https://www.eia.gov/opendata/register.php)",
                self.name,
            )
            return []

        records: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for spec in EIA_SERIES:
                await self.rate_limiter.acquire()
                url = f"{EIA_BASE_URL}/seriesid/{spec.series_id}"
                try:
                    resp = await client.get(
                        url,
                        params={
                            "api_key": self.api_key,
                            "length": self.lookback_periods,
                        },
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except Exception as exc:  # pragma: no cover - network
                    logger.warning(
                        "[%s] fetch failed for series %s: %s", self.name, spec.series_id, exc
                    )
                    continue
                parsed = parse_eia_response(spec, payload)
                records.extend(parsed)
                logger.info(
                    "[%s] %s (%s): %d stock reports", self.name, spec.commodity_code,
                    spec.series_id, len(parsed),
                )
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            r for r in records
            if r.get("commodity_code") and r.get("as_of_date") and r.get("stock_level") is not None
        ]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # parse_eia_response() already emits the final CommodityInventory
        # field shape; nothing further to normalize.
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                result = await session.execute(
                    select(CommodityInventory).where(
                        CommodityInventory.commodity_code == rec["commodity_code"],
                        CommodityInventory.as_of_date == rec["as_of_date"],
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.stock_level = rec["stock_level"]
                    existing.stock_unit = rec.get("stock_unit")
                    existing.metric_name = rec.get("metric_name")
                    existing.source = rec.get("source")
                    counts["updated"] += 1
                else:
                    session.add(CommodityInventory(**rec))
                    counts["inserted"] += 1
            except Exception:
                logger.exception(
                    "[%s] failed to load stock row for %s %s",
                    self.name, rec.get("commodity_code"), rec.get("as_of_date"),
                )
                counts["errors"] += 1
        await session.flush()
        return counts
