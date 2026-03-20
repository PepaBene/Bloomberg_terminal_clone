"""FINRA short interest data connector.

Fetches bi-weekly short interest data from FINRA and creates
ShortInterest records per security.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# FINRA short interest query API
FINRA_API_BASE = "https://api.finra.org/data/group/otcMarket/name/shortInterest"
FINRA_QUERY_URL = "https://api.finra.org/data/group/otcMarket/name/shortInterest"

# FINRA uses a query-based API; we also support a file-based fallback
FINRA_SHORT_INTEREST_URL = "https://api.finra.org/data/group/otcMarket/name/shortInterest"


class FinraShortInterestConnector(BaseConnector):
    """Ingest bi-weekly short interest data from FINRA."""

    name = "FINRA Short Interest"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(
        self,
        symbols: list[str] | None = None,
        settlement_date: str | None = None,
    ):
        """Initialize connector.

        Args:
            symbols: List of ticker symbols to fetch short interest for.
            settlement_date: Specific settlement date (YYYY-MM-DD). If None, fetches latest.
        """
        self.symbols = symbols or []
        self.settlement_date = settlement_date
        # FINRA rate limits are generally generous but we stay conservative
        self.rate_limiter = RateLimiter(max_requests=5, per_seconds=1.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _query_short_interest(
        self, symbol: str, settlement_date: str | None = None
    ) -> list[dict[str, Any]]:
        """Query FINRA short interest API for a single symbol.

        The FINRA API uses POST with a JSON body to query data.
        """
        await self.rate_limiter.acquire()
        client = await self._get_client()

        # Build FINRA query filters
        filters = [
            {"fieldName": "symbolCode", "fieldValue": symbol, "compareType": "EQUAL"},
        ]
        if settlement_date:
            filters.append({
                "fieldName": "settlementDate",
                "fieldValue": settlement_date,
                "compareType": "EQUAL",
            })

        query_body = {
            "fields": [
                "settlementDate",
                "symbolCode",
                "issueName",
                "currentShortPositionQuantity",
                "previousShortPositionQuantity",
                "changePreviousNumber",
                "changePercent",
                "averageDailyVolumeQuantity",
                "daysToCoverQuantity",
                "revisionFlag",
            ],
            "dateRangeFilters": [],
            "domainFilters": filters,
            "compareFilters": [],
            "orFilters": [],
            "limit": 10,
            "offset": 0,
            "sortFields": ["-settlementDate"],
        }

        try:
            resp = await client.post(FINRA_QUERY_URL, json=query_body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"FINRA API error for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying FINRA for {symbol}: {e}")
            return []

    async def extract(self) -> list[dict[str, Any]]:
        """Pull short interest data from FINRA for all configured symbols."""
        if not self.symbols:
            logger.warning("No symbols configured — skipping FINRA short interest extraction")
            return []

        records: list[dict[str, Any]] = []

        for symbol in self.symbols:
            try:
                data = await self._query_short_interest(
                    symbol, self.settlement_date
                )

                if not data:
                    logger.debug(f"  FINRA: No short interest data for {symbol}")
                    continue

                for entry in data:
                    entry["_symbol"] = symbol
                    records.append(entry)

                logger.info(f"  FINRA: {symbol} — {len(data)} short interest records")

            except Exception as e:
                logger.error(f"  FINRA: Failed to fetch {symbol}: {e}")

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate FINRA short interest records."""
        valid = []
        for rec in records:
            symbol = rec.get("_symbol") or rec.get("symbolCode")
            settlement = rec.get("settlementDate")
            short_qty = rec.get("currentShortPositionQuantity")

            if not symbol:
                continue
            if not settlement:
                continue
            if short_qty is None:
                continue

            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform FINRA data into our internal ShortInterest format."""
        transformed = []

        for rec in records:
            symbol = rec.get("_symbol") or rec.get("symbolCode", "")
            settlement = rec.get("settlementDate", "")
            current_short = rec.get("currentShortPositionQuantity")
            avg_volume = rec.get("averageDailyVolumeQuantity")
            days_to_cover = rec.get("daysToCoverQuantity")

            # Normalize settlement date format
            # FINRA may return dates as "YYYY-MM-DD" or "MM/DD/YYYY"
            settlement_date_str = settlement
            if "/" in settlement:
                try:
                    parts = settlement.split("/")
                    settlement_date_str = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                except (IndexError, ValueError):
                    pass

            transformed.append({
                "symbol": symbol,
                "settlement_date": settlement_date_str,
                "shares_short": float(current_short) if current_short is not None else None,
                "days_to_cover": float(days_to_cover) if days_to_cover is not None else None,
                "avg_daily_volume": float(avg_volume) if avg_volume is not None else None,
                # short_percent_float and short_percent_outstanding calculated
                # downstream once we have shares outstanding data
                "source": "FINRA",
            })

        logger.info(f"Transformed {len(transformed)} short interest records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write short interest records to database."""
        from src.models.ownership import ShortInterest
        from src.models.security import SecurityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                symbol = rec["symbol"]
                settlement_date_str = rec["settlement_date"]

                # Resolve security_id from ticker symbol
                result = await session.execute(
                    select(SecurityIdentifier).where(
                        SecurityIdentifier.identifier_type == "TICKER",
                        SecurityIdentifier.identifier_value == symbol,
                    )
                )
                sec_ident = result.scalar_one_or_none()
                if sec_ident is None:
                    logger.debug(f"No security found for ticker {symbol} — skipping")
                    stats["skipped"] += 1
                    continue
                security_id = sec_ident.security_id

                settlement_date_val = date.fromisoformat(settlement_date_str)

                # Check for duplicate
                existing = await session.execute(
                    select(ShortInterest).where(
                        ShortInterest.security_id == security_id,
                        ShortInterest.settlement_date == settlement_date_val,
                    )
                )
                existing_record = existing.scalar_one_or_none()

                if existing_record is not None:
                    # Update existing record
                    if rec.get("shares_short") is not None:
                        existing_record.shares_short = Decimal(str(rec["shares_short"]))
                    if rec.get("days_to_cover") is not None:
                        existing_record.days_to_cover = Decimal(str(rec["days_to_cover"]))
                    existing_record.source = "FINRA"
                    stats["updated"] += 1
                    continue

                short_interest = ShortInterest(
                    security_id=security_id,
                    settlement_date=settlement_date_val,
                    shares_short=Decimal(str(rec["shares_short"])) if rec.get("shares_short") is not None else None,
                    days_to_cover=Decimal(str(rec["days_to_cover"])) if rec.get("days_to_cover") is not None else None,
                    source="FINRA",
                )
                session.add(short_interest)
                stats["inserted"] += 1

            except Exception as e:
                logger.error(f"Error loading short interest for {rec.get('symbol')}: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
