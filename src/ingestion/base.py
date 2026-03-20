"""Base connector class for data ingestion pipelines (Spec 15.3)."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for all data source connectors."""

    name: str
    connector_type: str
    data_domain: str

    @abstractmethod
    async def extract(self) -> list[dict[str, Any]]:
        """Pull raw data from external source."""

    @abstractmethod
    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate raw records against expected schema."""

    @abstractmethod
    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize and transform records into internal format."""

    async def resolve(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Entity/security resolution (override in subclasses that need it)."""
        return records

    @abstractmethod
    async def load(self, records: list[dict[str, Any]], session: AsyncSession) -> dict[str, int]:
        """Write records to database. Returns counts: {inserted, updated, skipped, errors}."""

    async def run(
        self,
        session: AsyncSession,
        *,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> dict[str, int]:
        """Execute full pipeline: extract -> validate -> transform -> resolve -> load.

        Parameters
        ----------
        session : AsyncSession
            Database session for the load step.
        dry_run : bool
            If True, skip the load step and return zero counts.
        limit : int | None
            If set, cap the number of records processed after extraction.
        """
        self.dry_run = dry_run
        self.limit = limit
        logger.info(f"[{self.name}] Starting ingestion pipeline (dry_run={dry_run}, limit={limit})")

        try:
            raw = await self.extract()
            logger.info(f"[{self.name}] Extracted {len(raw)} records")

            if limit is not None:
                raw = raw[:limit]
                logger.info(f"[{self.name}] Limited to {len(raw)} records")

            valid = await self.validate(raw)
            logger.info(f"[{self.name}] Validated {len(valid)}/{len(raw)} records")

            transformed = await self.transform(valid)
            logger.info(f"[{self.name}] Transformed {len(transformed)} records")

            resolved = await self.resolve(transformed)
            logger.info(f"[{self.name}] Resolved {len(resolved)} records")

            if dry_run:
                stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0, "dry_run": True}
                logger.info(f"[{self.name}] Dry run — skipping load ({len(resolved)} records would be loaded)")
            else:
                stats = await self.load(resolved, session)
                logger.info(f"[{self.name}] Load complete: {stats}")

            return stats
        finally:
            if hasattr(self, 'close'):
                await self.close()
