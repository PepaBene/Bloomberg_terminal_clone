"""Ingest curated FRED commodity prices into commodity_profiles / commodity_prices."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fred_commodities import FredCommoditiesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = FredCommoditiesConnector(lookback_days=90)
    async with get_session_factory()() as session:
        logger.info("Starting FRED commodities ingestion...")
        stats = await connector.run(session)
        # BaseConnector.run only flushes — commit or the data is rolled back.
        await session.commit()
        logger.info(f"Commodities ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
