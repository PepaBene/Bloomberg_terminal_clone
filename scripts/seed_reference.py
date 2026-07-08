"""Seed reference data from static JSON files into the database."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.reference_loader import load_all_reference_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting reference data seed...")
    async with get_session_factory()() as session:
        results = await load_all_reference_data(session)
        # load_all_reference_data only flushes; commit here or the whole seed
        # is rolled back when the session closes.
        await session.commit()
        logger.info("Seed complete.")
        for name, stats in results.items():
            logger.info(f"  {name}: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
