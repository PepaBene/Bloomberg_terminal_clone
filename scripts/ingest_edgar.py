"""Ingest entities from SEC EDGAR."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_entities import EdgarEntityConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = EdgarEntityConnector()
    async with get_session_factory()() as session:
        logger.info("Starting SEC EDGAR entity ingestion...")
        stats = await connector.run(session)
        await session.commit()
        logger.info(f"EDGAR ingestion complete: {stats}")

        # Optionally enrich with per-company detail
        logger.info("Enriching entities with EDGAR detail (first 100)...")
        enrich_stats = await connector.enrich_with_details(session, max_entities=100)
        await session.commit()
        logger.info(f"Enrichment complete: {enrich_stats}")


if __name__ == "__main__":
    asyncio.run(main())
