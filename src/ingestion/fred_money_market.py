"""Money Market Rate ingestion from FRED (Part 2).

FRED series: SOFR, DFF, DFEDTAR, DTB3, DTB6, DTB1YR, DCPF3M, DCPN3M, DPRIME.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

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

    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests=settings.FRED_RATE_LIMIT if hasattr(settings, "FRED_RATE_LIMIT") else 10,
            per_seconds=1.0,
        )

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch money market rates from FRED."""
        records: list[dict[str, Any]] = []
        # Skeleton — production would use FRED API with the configured API key.
        logger.info("FRED money market extraction queued for %d series", len(FRED_SERIES_MAP))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate money market rate records."""
        valid = []
        for rec in records:
            if not rec.get("rate_date") or not rec.get("rate_type"):
                continue
            if rec.get("rate_value") is None:
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform FRED series observations to internal format."""
        transformed = []
        for rec in records:
            # Convert FRED percentage (e.g. 5.33) to decimal (e.g. 0.0533)
            if rec.get("rate_value") is not None and rec.get("rate_value") > 1:
                rec["rate_value"] = rec["rate_value"] / 100.0
            transformed.append(rec)
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load money market rates."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for rec in records:
            try:
                from src.models.fed_meeting import MoneyMarketRate

                rate = MoneyMarketRate(
                    rate_date=rec["rate_date"],
                    rate_type=rec["rate_type"],
                    rate_value=rec["rate_value"],
                    source=rec.get("source", "FRED"),
                )
                session.add(rate)
                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading money market rate: %s", e)
                stats["errors"] += 1
        return stats
