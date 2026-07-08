"""GLEIF LEI entity ingestion connector.

Fetches Legal Entity Identifiers from GLEIF Golden Copy API:
- Search API: https://api.gleif.org/api/v1/lei-records
- Bulk download: https://leidata.gleif.org/api/v1/concatenated-files/lei2/get/{date}/zip
"""

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.entity import Entity, EntityIdentifier
from src.resolution.resolver import resolve
from src.temporal.pit import record_entity_history

logger = logging.getLogger(__name__)

GLEIF_API_URL = "https://api.gleif.org/api/v1/lei-records"


def _extract_parent_lei(relationships: dict, key: str) -> str | None:
    """Pull the parent LEI out of a GLEIF JSON:API relationship block.

    GLEIF Level-2 records expose ``direct-parent`` / ``ultimate-parent``
    relationships whose ``links.lei-record`` points at the parent's own
    LEI record (``.../lei-records/{PARENT_LEI}``). When the entity reports
    a parent-disclosure *exception* instead, only a ``reporting-exception``
    link is present and there is no parent LEI to extract.
    """
    block = (relationships or {}).get(key) or {}
    lei_record_url = (block.get("links") or {}).get("lei-record")
    if not lei_record_url:
        return None
    parent_lei = lei_record_url.rstrip("/").rsplit("/", 1)[-1].strip()
    return parent_lei or None


class GleifEntityConnector(BaseConnector):
    name = "GLEIF LEI"
    connector_type = "BATCH_API"
    data_domain = "ENTITY"

    def __init__(self, country_filter: str = "US", page_size: int = 200, max_pages: int = 50):
        self.country_filter = country_filter
        self.page_size = page_size
        self.max_pages = max_pages
        self.rate_limiter = RateLimiter(max_requests=5, per_seconds=1.0)

    async def extract(self) -> list[dict[str, Any]]:
        """Fetch LEI records from GLEIF API with pagination."""
        records = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while page <= self.max_pages:
                await self.rate_limiter.acquire()
                params = {
                    "filter[entity.legalAddress.country]": self.country_filter,
                    "filter[registration.status]": "ISSUED",
                    "page[size]": self.page_size,
                    "page[number]": page,
                }
                try:
                    resp = await client.get(GLEIF_API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as e:
                    logger.error(f"GLEIF API error on page {page}: {e}")
                    break

                batch = data.get("data", [])
                if not batch:
                    break

                records.extend(batch)
                logger.info(f"Fetched page {page}: {len(batch)} records (total: {len(records)})")

                # Check if there are more pages
                links = data.get("links", {})
                if not links.get("next"):
                    break
                page += 1

        logger.info(f"Extracted {len(records)} LEI records from GLEIF")
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate GLEIF records."""
        valid = []
        for r in records:
            attrs = r.get("attributes", {})
            entity_data = attrs.get("entity", {})
            lei = attrs.get("lei", "")

            if lei and entity_data.get("legalName", {}).get("name"):
                valid.append(r)
            else:
                logger.debug(f"Skipping invalid GLEIF record: {r.get('id', 'unknown')}")
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform GLEIF records into internal entity format."""
        transformed = []
        for r in records:
            attrs = r.get("attributes", {})
            entity_data = attrs.get("entity", {})
            registration = attrs.get("registration", {})
            relationships = r.get("relationships", {})

            legal_name = entity_data.get("legalName", {}).get("name", "")
            lei = attrs.get("lei", "")

            # Address
            legal_addr = entity_data.get("legalAddress", {})
            address = {
                "street1": legal_addr.get("addressLines", [""])[0] if legal_addr.get("addressLines") else "",
                "city": legal_addr.get("city", ""),
                "region": legal_addr.get("region", ""),
                "postal_code": legal_addr.get("postalCode", ""),
                "country": legal_addr.get("country", ""),
            }

            # Map GLEIF entity category to our type
            category = entity_data.get("category", "")
            entity_type = self._map_entity_type(category)

            transformed.append(
                {
                    "legal_name": legal_name,
                    "lei": lei,
                    "entity_type": entity_type,
                    "status": "ACTIVE",
                    "country": legal_addr.get("country", ""),
                    "address": address,
                    "source": "GLEIF",
                    "registration_date": registration.get("initialRegistrationDate"),
                    # Level-2 corporate hierarchy (parent LEIs) when disclosed
                    "immediate_parent_lei": _extract_parent_lei(
                        relationships, "direct-parent"
                    ),
                    "ultimate_parent_lei": _extract_parent_lei(
                        relationships, "ultimate-parent"
                    ),
                }
            )
        return transformed

    async def resolve(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run entity resolution to match against existing entities."""
        # Resolution happens during load — just pass through
        return records

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load GLEIF entities, resolving against existing DB records."""
        stats = {"matched": 0, "created": 0, "uncertain": 0, "errors": 0}

        for record in records:
            try:
                lei = record["lei"]

                # Check if LEI already exists
                existing = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "LEI",
                        EntityIdentifier.identifier_value == lei,
                    )
                )
                if existing.scalar_one_or_none():
                    stats["matched"] += 1
                    continue

                # Try to resolve against existing entities. UNCERTAIN verdicts
                # are enqueued for human review inside resolve() itself.
                resolution = await resolve(
                    legal_name=record["legal_name"],
                    country=record.get("country"),
                    identifiers={"LEI": lei},
                    session=session,
                    source_system="GLEIF",
                )

                if resolution.status == "MATCHED" and resolution.entity_id:
                    # Add LEI to existing entity
                    session.add(
                        EntityIdentifier(
                            id=uuid.uuid4(),
                            entity_id=resolution.entity_id,
                            identifier_type="LEI",
                            identifier_value=lei,
                            source="GLEIF",
                            is_primary=True,
                        )
                    )
                    # Populate corporate hierarchy on the matched entity
                    matched = await session.get(Entity, resolution.entity_id)
                    if matched is not None:
                        await self._apply_parents(matched, record, session)
                        await record_entity_history(matched, session)
                    stats["matched"] += 1

                elif resolution.status == "UNCERTAIN":
                    # Uncertain match — resolve() has parked it on the review
                    # queue (resolution_queue); surfaced via /resolution/queue.
                    stats["uncertain"] += 1

                else:
                    # Create new entity
                    entity_id = uuid.uuid4()
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=record["entity_type"],
                        legal_name=record["legal_name"],
                        status=record["status"],
                        incorporation_country=record.get("country"),
                        domicile_address=record.get("address"),
                        source="GLEIF",
                    )
                    session.add(entity)

                    session.add(
                        EntityIdentifier(
                            id=uuid.uuid4(),
                            entity_id=entity_id,
                            identifier_type="LEI",
                            identifier_value=lei,
                            source="GLEIF",
                            is_primary=True,
                        )
                    )
                    # Populate corporate hierarchy from GLEIF parent LEIs and
                    # snapshot the initial state into entity history.
                    await self._apply_parents(entity, record, session)
                    await record_entity_history(entity, session)
                    stats["created"] += 1

            except Exception as e:
                logger.error(f"Error loading GLEIF record {record.get('lei', '?')}: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    @staticmethod
    async def _lookup_entity_by_lei(
        lei: str | None, session: AsyncSession
    ) -> uuid.UUID | None:
        """Resolve a parent LEI to a local entity_id, if it is already loaded."""
        if not lei:
            return None
        result = await session.execute(
            select(EntityIdentifier.entity_id).where(
                EntityIdentifier.identifier_type == "LEI",
                EntityIdentifier.identifier_value == lei,
            )
        )
        return result.scalar_one_or_none()

    async def _apply_parents(
        self, entity: Entity, record: dict[str, Any], session: AsyncSession
    ) -> None:
        """Set immediate/ultimate parent ids from GLEIF parent LEIs.

        Parents are only set when the referenced LEI is already present in
        our entity master (best-effort). Self-references are skipped. GLEIF is
        the one source with clean parent-LEI data; EDGAR has no comparable
        parent linkage, which is why EDGAR entities carry no hierarchy.
        """
        imm_id = await self._lookup_entity_by_lei(
            record.get("immediate_parent_lei"), session
        )
        ult_id = await self._lookup_entity_by_lei(
            record.get("ultimate_parent_lei"), session
        )
        if imm_id and imm_id != entity.entity_id:
            entity.immediate_parent_id = imm_id
        if ult_id and ult_id != entity.entity_id:
            entity.ultimate_parent_id = ult_id

    @staticmethod
    def _map_entity_type(gleif_category: str) -> str:
        """Map GLEIF entity category to our EntityType."""
        mapping = {
            "FUND": "FUND",
            "BRANCH": "OTHER",
            "SOLE_PROPRIETOR": "PRIVATE_COMPANY",
            "INTERNATIONAL_ORGANIZATION": "SUPRANATIONAL",
            "GENERAL": "PUBLIC_COMPANY",  # Default assumption
        }
        return mapping.get(gleif_category, "OTHER")
