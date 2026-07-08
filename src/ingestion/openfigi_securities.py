"""OpenFIGI security ingestion connector.

Maps tickers to FIGI identifiers via the OpenFIGI API:
- Endpoint: https://api.openfigi.com/v3/mapping
- Batch: up to 100 identifiers per POST
"""

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.entity import Entity, EntityIdentifier, EntityName
from src.models.security import EquityDetails, Security, SecurityIdentifier

logger = logging.getLogger(__name__)

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
BATCH_SIZE = 100


class OpenFigiSecurityConnector(BaseConnector):
    name = "OpenFIGI Securities"
    connector_type = "BATCH_API"
    data_domain = "SECURITY"

    def __init__(self):
        rate = settings.openfigi_effective_rate_limit
        # Convert per-minute rate to per-second
        self.rate_limiter = RateLimiter(
            max_requests=max(1, rate // 60), per_seconds=1.0
        )
        self.headers = {"Content-Type": "application/json"}
        if settings.OPENFIGI_API_KEY:
            self.headers["X-OPENFIGI-APIKEY"] = settings.OPENFIGI_API_KEY

    async def extract(self) -> list[dict[str, Any]]:
        """Not used directly — extraction is done in run() with batching."""
        return []

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return records

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Not used directly — loading is done per-batch in run()."""
        return {}

    async def run(self, session: AsyncSession) -> dict[str, int]:
        """Full pipeline: get tickers from entities, batch query OpenFIGI, create securities."""
        stats = {"inserted": 0, "skipped": 0, "errors": 0}

        # Get all tickers from entity trading names
        ticker_result = await session.execute(
            select(EntityName, Entity)
            .join(Entity, EntityName.entity_id == Entity.entity_id)
            .where(
                EntityName.name_type == "TRADING",
                Entity.status == "ACTIVE",
            )
        )
        ticker_rows = ticker_result.all()

        if not ticker_rows:
            logger.warning("No tickers found in entity trading names")
            return stats

        # Build ticker -> entity_id mapping
        ticker_map: dict[str, tuple[uuid.UUID, str]] = {}
        for name_record, entity in ticker_rows:
            ticker = name_record.name_value.strip().upper()
            if ticker:
                ticker_map[ticker] = (entity.entity_id, entity.legal_name)

        tickers = list(ticker_map.keys())

        # Resumability: skip tickers we've already mapped to a security so a
        # re-run only fetches what's missing (and doesn't waste API calls).
        existing = set(
            (
                await session.execute(
                    select(SecurityIdentifier.identifier_value).where(
                        SecurityIdentifier.identifier_type == "TICKER"
                    )
                )
            )
            .scalars()
            .all()
        )
        if existing:
            before = len(tickers)
            tickers = [t for t in tickers if t not in existing]
            logger.info("Skipping %d already-mapped tickers", before - len(tickers))
        logger.info(f"Found {len(tickers)} tickers to look up via OpenFIGI")

        # Process in batches
        for i in range(0, len(tickers), BATCH_SIZE):
            batch = tickers[i : i + BATCH_SIZE]
            batch_results = await self._query_openfigi(batch)

            for ticker, figi_data in zip(batch, batch_results):
                if not figi_data or "data" not in figi_data or not figi_data["data"]:
                    stats["skipped"] += 1
                    continue

                # OpenFIGI returns several overlapping results per ticker
                # (composite, share-class, per-venue listings). Use the first
                # (primary) so a ticker maps to a single security and we don't
                # collide on the unique (identifier_type, identifier_value).
                item = figi_data["data"][0]
                try:
                    # Savepoint per ticker: a duplicate/constraint failure rolls
                    # back just this record instead of poisoning the whole batch.
                    async with session.begin_nested():
                        result = await self._create_security(
                            ticker, item, ticker_map.get(ticker), session
                        )
                        await session.flush()
                    if result:
                        stats["inserted"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.debug(f"Skipped security for {ticker}: {e}")
                    stats["skipped"] += 1

            # Commit each batch so partial progress persists and a later failure
            # doesn't lose everything (and keeps transactions small).
            await session.commit()
            logger.info(
                f"Processed batch {i // BATCH_SIZE + 1}: "
                f"{stats['inserted']} inserted, {stats['skipped']} skipped"
            )

        return stats

    async def _query_openfigi(
        self, tickers: list[str]
    ) -> list[dict[str, Any] | None]:
        """Query OpenFIGI API for a batch of tickers."""
        jobs = [
            {"idType": "TICKER", "idValue": t, "exchCode": "US"} for t in tickers
        ]

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            await self.rate_limiter.acquire()
            try:
                resp = await client.post(OPENFIGI_URL, json=jobs)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as e:
                logger.error(f"OpenFIGI API error: {e}")
                return [None] * len(tickers)

    async def _create_security(
        self,
        ticker: str,
        figi_item: dict[str, Any],
        entity_info: tuple[uuid.UUID, str] | None,
        session: AsyncSession,
    ) -> bool:
        """Create a security record from an OpenFIGI result."""
        figi = figi_item.get("figi", "")
        if not figi:
            return False

        # Check if FIGI already exists
        existing = await session.execute(
            select(SecurityIdentifier).where(
                SecurityIdentifier.identifier_type == "FIGI",
                SecurityIdentifier.identifier_value == figi,
            )
        )
        if existing.scalar_one_or_none():
            return False

        # Map OpenFIGI security type to our type
        sec_type_raw = figi_item.get("securityType", "")
        sec_type, asset_class = self._map_security_type(sec_type_raw)

        security_id = uuid.uuid4()
        entity_id = entity_info[0] if entity_info else None
        entity_name = entity_info[1] if entity_info else ""

        # OpenFIGI's exchCode is its own code (e.g. "UN"/"UW"), NOT an ISO MIC,
        # so it never matches exchanges.mic and would violate the FK. Map the
        # common US venues to the real MICs we seed and null anything else.
        _exch_to_mic = {"UN": "XNYS", "UW": "XNAS", "UQ": "XNAS", "UR": "XNAS", "UF": "XNAS"}
        exch_mic = _exch_to_mic.get(figi_item.get("exchCode") or "")

        security = Security(
            security_id=security_id,
            security_type=sec_type,
            issuer_entity_id=entity_id,
            name=figi_item.get("name", f"{ticker} - {sec_type}"),
            short_name=ticker,
            status="ACTIVE",
            asset_class=asset_class,
            primary_exchange_mic=exch_mic,
            primary_currency="USD",
        )
        session.add(security)

        # Add identifiers
        identifiers_to_add = [
            ("FIGI", figi),
            ("COMPOSITE_FIGI", figi_item.get("compositeFIGI", "")),
            ("SHARE_CLASS_FIGI", figi_item.get("shareClassFIGI", "")),
            ("TICKER", ticker),
        ]
        for id_type, id_value in identifiers_to_add:
            if id_value:
                session.add(
                    SecurityIdentifier(
                        id=uuid.uuid4(),
                        security_id=security_id,
                        identifier_type=id_type,
                        identifier_value=id_value,
                        source="OPENFIGI",
                    )
                )

        # Create equity details for equity securities
        if asset_class == "EQUITY":
            session.add(EquityDetails(security_id=security_id))

        return True

    @staticmethod
    def _map_security_type(openfigi_type: str) -> tuple[str, str]:
        """Map OpenFIGI security type to our SecurityType and AssetClass."""
        type_map = {
            "Common Stock": ("COMMON_STOCK", "EQUITY"),
            "Preferred Stock": ("PREFERRED_STOCK", "EQUITY"),
            "DEPOSITARY RECEIPT": ("DEPOSITARY_RECEIPT", "EQUITY"),
            "REIT": ("REIT", "EQUITY"),
            "MLP": ("MLP", "EQUITY"),
            "ETP": ("ETF", "FUND"),
            "Open-End Fund": ("MUTUAL_FUND", "FUND"),
            "Closed-End Fund": ("MUTUAL_FUND", "FUND"),
            "Index": ("INDEX", "INDEX"),
            "Corp": ("CORPORATE_BOND", "FIXED_INCOME"),
            "Govt": ("GOVERNMENT_BOND", "FIXED_INCOME"),
            "Muni": ("MUNICIPAL_BOND", "FIXED_INCOME"),
        }
        result = type_map.get(openfigi_type, ("COMMON_STOCK", "EQUITY"))
        return result
