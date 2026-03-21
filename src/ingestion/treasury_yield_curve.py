"""Treasury Yield Curve ingestion from Treasury.gov / FRED (Part 2).

Fetches daily Treasury yield curve rates and computes derived spreads.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Treasury.gov XML feed tenors mapped to model fields
TENOR_FIELD_MAP = {
    "1 Mo": "rate_1m",
    "3 Mo": "rate_3m",
    "6 Mo": "rate_6m",
    "1 Yr": "rate_1y",
    "2 Yr": "rate_2y",
    "3 Yr": "rate_3y",
    "5 Yr": "rate_5y",
    "7 Yr": "rate_7y",
    "10 Yr": "rate_10y",
    "20 Yr": "rate_20y",
    "30 Yr": "rate_30y",
}


def compute_spreads(rec: dict[str, Any]) -> dict[str, Any]:
    """Compute derived spread metrics from raw rates."""
    rate_2y = rec.get("rate_2y")
    rate_10y = rec.get("rate_10y")
    rate_3m = rec.get("rate_3m")

    if rate_2y is not None and rate_10y is not None:
        rec["spread_2s10s"] = rate_10y - rate_2y
        rec["is_inverted"] = rec["spread_2s10s"] < 0
    if rate_3m is not None and rate_10y is not None:
        rec["spread_3m10y"] = rate_10y - rate_3m

    return rec


class TreasuryYieldCurveConnector(BaseConnector):
    """Fetch daily Treasury yield curve rates."""

    name = "Treasury Yield Curve"
    connector_type = "BATCH_API"
    data_domain = "YIELD_CURVE"

    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests=settings.FRED_RATE_LIMIT if hasattr(settings, "FRED_RATE_LIMIT") else 10,
            per_seconds=1.0,
        )

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch yield curve data from Treasury.gov / FRED."""
        records: list[dict[str, Any]] = []
        # Skeleton — production would fetch from Treasury.gov XML or FRED API.
        logger.info("Treasury yield curve extraction queued")
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate yield curve records."""
        valid = []
        for rec in records:
            if not rec.get("curve_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute spreads and inversion flags."""
        return [compute_spreads(rec) for rec in records]

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load yield curve snapshots."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for rec in records:
            try:
                from src.models.yield_curve import YieldCurveSnapshot

                snapshot = YieldCurveSnapshot(
                    curve_date=rec["curve_date"],
                    curve_type=rec.get("curve_type", "TREASURY_NOMINAL"),
                    rate_1m=rec.get("rate_1m"),
                    rate_3m=rec.get("rate_3m"),
                    rate_6m=rec.get("rate_6m"),
                    rate_1y=rec.get("rate_1y"),
                    rate_2y=rec.get("rate_2y"),
                    rate_3y=rec.get("rate_3y"),
                    rate_5y=rec.get("rate_5y"),
                    rate_7y=rec.get("rate_7y"),
                    rate_10y=rec.get("rate_10y"),
                    rate_20y=rec.get("rate_20y"),
                    rate_30y=rec.get("rate_30y"),
                    spread_2s10s=rec.get("spread_2s10s"),
                    spread_3m10y=rec.get("spread_3m10y"),
                    curve_slope=rec.get("curve_slope"),
                    is_inverted=rec.get("is_inverted", False),
                    source=rec.get("source", "TREASURY_GOV"),
                )
                session.add(snapshot)
                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading yield curve: %s", e)
                stats["errors"] += 1
        return stats
