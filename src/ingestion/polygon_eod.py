"""Polygon.io EOD price connector (Spec 15.3).

Fetches end-of-day price data from Polygon.io REST API:
- Grouped daily endpoint: /v2/aggs/grouped/locale/us/market/stocks/{date}
- Maps Polygon tickers to internal security_ids via SecurityIdentifier lookup

Creates EODPrice records in src/models/security.py.

Config: POLYGON_API_KEY, rate limit 5 req/sec (free tier).
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

POLYGON_BASE_URL = "https://api.polygon.io"
GROUPED_DAILY_URL = (
    f"{POLYGON_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks/{{date}}"
)


class PolygonEODConnector(BaseConnector):
    """Ingest end-of-day price data from Polygon.io."""

    name = "Polygon EOD"
    connector_type = "BATCH_API"
    data_domain = "SECURITY_PRICES"

    def __init__(
        self,
        api_key: str | None = None,
        target_date: str | None = None,
    ) -> None:
        """Initialize Polygon EOD connector.

        Args:
            api_key: Polygon.io API key. Falls back to settings.POLYGON_API_KEY.
            target_date: Date string (YYYY-MM-DD) to fetch prices for.
                         Defaults to most recent trading day.
        """
        self.api_key = api_key or getattr(settings, "POLYGON_API_KEY", "")
        self.target_date = target_date
        polygon_rate_limit = getattr(settings, "POLYGON_RATE_LIMIT", 5)
        self.rate_limiter = RateLimiter(
            max_requests=polygon_rate_limit, per_seconds=1.0
        )
        self._client: httpx.AsyncClient | None = None
        # Ticker-to-security_id mapping, populated during resolve()
        self._ticker_map: dict[str, uuid.UUID] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _polygon_get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a rate-limited GET request to Polygon.io API."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        all_params: dict[str, Any] = {"apiKey": self.api_key}
        if params:
            all_params.update(params)
        resp = await client.get(url, params=all_params)
        resp.raise_for_status()
        return resp.json()

    async def extract(self) -> list[dict[str, Any]]:
        """Pull grouped daily EOD prices from Polygon.io."""
        if not self.api_key:
            logger.warning("POLYGON_API_KEY not set — skipping extraction")
            return []

        if not self.target_date:
            # Default to yesterday (most recent completed trading day)
            from datetime import timedelta

            yesterday = date.today() - timedelta(days=1)
            self.target_date = yesterday.isoformat()

        url = GROUPED_DAILY_URL.format(date=self.target_date)

        try:
            data = await self._polygon_get(url, params={"adjusted": "true"})
        except httpx.HTTPStatusError as e:
            logger.error(
                "Polygon grouped daily request failed for %s: %s",
                self.target_date,
                e,
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error fetching Polygon EOD for %s: %s",
                self.target_date,
                e,
            )
            return []

        results = data.get("results", [])
        logger.info(
            "  Polygon: Fetched %d ticker prices for %s",
            len(results),
            self.target_date,
        )

        # Convert Polygon response to our raw record format
        records: list[dict[str, Any]] = []
        for item in results:
            ticker = item.get("T", "")
            if not ticker:
                continue

            records.append({
                "ticker": ticker,
                "price_date": self.target_date,
                "open": item.get("o"),
                "high": item.get("h"),
                "low": item.get("l"),
                "close": item.get("c"),
                "volume": item.get("v"),
                "vwap": item.get("vw"),
                "num_transactions": item.get("n"),
            })

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate raw price records — filter out entries with missing data."""
        valid: list[dict[str, Any]] = []
        for rec in records:
            if not rec.get("ticker"):
                continue
            if not rec.get("price_date"):
                continue
            # Must have at least a close price
            if rec.get("close") is None:
                continue
            # Sanity checks
            close = rec["close"]
            if not isinstance(close, (int, float)) or close <= 0:
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform Polygon records into EODPrice format."""
        transformed: list[dict[str, Any]] = []

        for rec in records:
            transformed.append({
                "ticker": rec["ticker"],
                "price_date": rec["price_date"],
                "open": rec.get("open"),
                "high": rec.get("high"),
                "low": rec.get("low"),
                "close": rec.get("close"),
                "close_adjusted": rec.get("close"),  # Polygon adjusted=true
                "volume": int(rec["volume"]) if rec.get("volume") is not None else None,
                "currency": "USD",
                "source": "POLYGON",
            })

        return transformed

    async def resolve(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map Polygon tickers to internal security_ids.

        Overrides BaseConnector.resolve() to perform SecurityIdentifier
        lookup for each ticker, filtering out unrecognized tickers.
        """
        # This mapping is built during load via session, but we can
        # pre-filter here if the ticker map has been populated.
        # For now, pass through — resolution happens in load().
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write EODPrice records to the database.

        Resolves tickers to security_ids via SecurityIdentifier lookup.
        """
        from src.models.security import EODPrice, SecurityIdentifier

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Build ticker -> security_id map from database
        if not self._ticker_map:
            result = await session.execute(
                select(SecurityIdentifier).where(
                    SecurityIdentifier.identifier_type == "TICKER"
                )
            )
            for row in result.scalars().all():
                self._ticker_map[row.identifier_value.upper()] = row.security_id

            logger.info(
                "  Polygon: Built ticker map with %d securities",
                len(self._ticker_map),
            )

        for rec in records:
            try:
                ticker = rec["ticker"].upper()
                security_id = self._ticker_map.get(ticker)

                if security_id is None:
                    # Unknown ticker — not in our security master
                    stats["skipped"] += 1
                    continue

                price_date = date.fromisoformat(rec["price_date"])

                # Check for existing EOD price (composite PK: security_id + price_date)
                existing = await session.execute(
                    select(EODPrice).where(
                        EODPrice.security_id == security_id,
                        EODPrice.price_date == price_date,
                    )
                )
                existing_price = existing.scalar_one_or_none()

                if existing_price is not None:
                    # Update existing record
                    existing_price.open = Decimal(str(rec["open"])) if rec.get("open") is not None else None
                    existing_price.high = Decimal(str(rec["high"])) if rec.get("high") is not None else None
                    existing_price.low = Decimal(str(rec["low"])) if rec.get("low") is not None else None
                    existing_price.close = Decimal(str(rec["close"])) if rec.get("close") is not None else None
                    existing_price.close_adjusted = Decimal(str(rec["close_adjusted"])) if rec.get("close_adjusted") is not None else None
                    existing_price.volume = rec.get("volume")
                    existing_price.source = "POLYGON"
                    stats["updated"] += 1
                else:
                    # Insert new EOD price
                    eod = EODPrice(
                        security_id=security_id,
                        price_date=price_date,
                        open=Decimal(str(rec["open"])) if rec.get("open") is not None else None,
                        high=Decimal(str(rec["high"])) if rec.get("high") is not None else None,
                        low=Decimal(str(rec["low"])) if rec.get("low") is not None else None,
                        close=Decimal(str(rec["close"])) if rec.get("close") is not None else None,
                        close_adjusted=Decimal(str(rec["close_adjusted"])) if rec.get("close_adjusted") is not None else None,
                        volume=rec.get("volume"),
                        currency=rec.get("currency", "USD"),
                        source="POLYGON",
                    )
                    session.add(eod)
                    stats["inserted"] += 1

            except Exception as e:
                logger.debug("Skip EOD price for %s: %s", rec.get("ticker"), e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
