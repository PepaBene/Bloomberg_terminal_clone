"""Ingest entities from GLEIF LEI database."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.gleif_entities import GleifEntityConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = GleifEntityConnector(country_filter="US", max_pages=10)
    async with get_session_factory()() as session:
        logger.info("Starting GLEIF LEI entity ingestion...")
        stats = await connector.run(session)
        await session.commit()
        logger.info(f"GLEIF ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
