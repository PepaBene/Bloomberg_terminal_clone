"""SEC EDGAR entity ingestion connector (Spec 15.3).

Fetches public company data from SEC EDGAR:
- Bulk company list: https://www.sec.gov/files/company_tickers.json
- Per-company detail: https://data.sec.gov/submissions/CIK{padded}.json
"""

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.entity import Entity, EntityIdentifier, EntityName
from src.temporal.pit import record_entity_history

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class EdgarEntityConnector(BaseConnector):
    name = "SEC EDGAR Entities"
    connector_type = "BATCH_API"
    data_domain = "ENTITY"

    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch bulk company tickers list from SEC EDGAR."""
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            await self.rate_limiter.acquire()
            resp = await client.get(COMPANY_TICKERS_URL)
            resp.raise_for_status()
            data = resp.json()

        # data is {0: {cik_str, ticker, title}, 1: {...}, ...}
        records = []
        for _idx, entry in data.items():
            records.append(
                {
                    "cik": str(entry["cik_str"]),
                    "ticker": entry.get("ticker", ""),
                    "title": entry.get("title", ""),
                }
            )

        logger.info(f"Extracted {len(records)} companies from SEC EDGAR bulk list")
        return records

    async def extract_detail(self, cik: str) -> dict[str, Any] | None:
        """Fetch detailed submission data for a single company."""
        padded_cik = cik.zfill(10)
        url = SUBMISSIONS_URL.format(cik=padded_cik)

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            await self.rate_limiter.acquire()
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"Failed to fetch detail for CIK {cik}: {e}")
                return None

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out records with missing required fields."""
        valid = []
        for r in records:
            if r.get("cik") and r.get("title"):
                valid.append(r)
            else:
                logger.debug(f"Skipping invalid record: {r}")
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform EDGAR records into entity format."""
        transformed = []
        for r in records:
            entity = {
                "legal_name": r["title"],
                "entity_type": "PUBLIC_COMPANY",
                "status": "ACTIVE",
                "source": "SEC_EDGAR",
                "identifiers": [
                    {"type": "CIK", "value": r["cik"], "source": "SEC_EDGAR"}
                ],
            }
            if r.get("ticker"):
                entity["trading_name"] = r["ticker"]
            transformed.append(entity)
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load entities into database with upsert on CIK."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for record in records:
            try:
                cik = record["identifiers"][0]["value"]

                # Check if entity with this CIK already exists
                existing = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                existing_id = existing.scalar_one_or_none()

                if existing_id:
                    # Update existing entity
                    entity = await session.get(Entity, existing_id.entity_id)
                    if entity:
                        changed = (
                            entity.legal_name != record["legal_name"]
                            or entity.status != record["status"]
                        )
                        entity.legal_name = record["legal_name"]
                        entity.status = record["status"]
                        # Snapshot the prior/new state into entity history so
                        # /entities/{id}/history and PIT queries have real rows.
                        if changed:
                            await record_entity_history(entity, session)
                        stats["updated"] += 1
                    continue

                # Create new entity
                entity_id = uuid.uuid4()
                entity = Entity(
                    entity_id=entity_id,
                    entity_type=record["entity_type"],
                    legal_name=record["legal_name"],
                    status=record["status"],
                    source=record["source"],
                )
                session.add(entity)

                # Add CIK identifier
                session.add(
                    EntityIdentifier(
                        id=uuid.uuid4(),
                        entity_id=entity_id,
                        identifier_type="CIK",
                        identifier_value=cik,
                        source="SEC_EDGAR",
                        is_primary=True,
                    )
                )

                # Add trading name if ticker exists
                if record.get("trading_name"):
                    session.add(
                        EntityName(
                            id=uuid.uuid4(),
                            entity_id=entity_id,
                            name_type="TRADING",
                            name_value=record["trading_name"],
                            source="SEC_EDGAR",
                        )
                    )

                stats["inserted"] += 1

            except Exception as e:
                logger.error(f"Error loading entity: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def enrich_with_details(
        self, session: AsyncSession, max_entities: int = 100
    ) -> dict[str, int]:
        """Fetch per-company detail from EDGAR and enrich existing entities.

        This is a separate pass that adds: SIC code, fiscal_year_end,
        incorporation_state, address, etc.
        """
        stats = {"enriched": 0, "skipped": 0, "errors": 0}

        # Get entities that came from EDGAR
        result = await session.execute(
            select(Entity, EntityIdentifier)
            .join(
                EntityIdentifier,
                Entity.entity_id == EntityIdentifier.entity_id,
            )
            .where(
                EntityIdentifier.identifier_type == "CIK",
                Entity.source == "SEC_EDGAR",
                Entity.primary_sic.is_(None),  # Not yet enriched
            )
            .limit(max_entities)
        )
        rows = result.all()

        for entity, identifier in rows:
            try:
                detail = await self.extract_detail(identifier.identifier_value)
                if not detail:
                    stats["skipped"] += 1
                    continue

                # Enrich entity with detail data
                if detail.get("sic"):
                    entity.primary_sic = detail["sic"]
                if detail.get("fiscalYearEnd"):
                    # EDGAR returns "1231" format, convert to "12-31"
                    fye = detail["fiscalYearEnd"]
                    if len(fye) == 4:
                        entity.fiscal_year_end = f"{fye[:2]}-{fye[2:]}"
                if detail.get("stateOfIncorporation"):
                    entity.incorporation_state = detail["stateOfIncorporation"]

                # Extract address
                addresses = detail.get("addresses", {})
                if addresses.get("business"):
                    biz = addresses["business"]
                    entity.domicile_address = {
                        "street1": biz.get("street1", ""),
                        "street2": biz.get("street2", ""),
                        "city": biz.get("city", ""),
                        "state": biz.get("stateOrCountry", ""),
                        "zip": biz.get("zipCode", ""),
                    }

                # Set country for US entities
                state = detail.get("stateOfIncorporation", "")
                if len(state) == 2 and state.isalpha():
                    entity.incorporation_country = "US"

                stats["enriched"] += 1

            except Exception as e:
                logger.error(
                    f"Error enriching CIK {identifier.identifier_value}: {e}"
                )
                stats["errors"] += 1

        await session.flush()
        return stats
