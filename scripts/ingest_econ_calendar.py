"""Ingest the FRED economic-release calendar into economic_releases."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fred_econ_calendar import FredEconCalendarConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = FredEconCalendarConnector(lookback_days=90, lookahead_days=180)
    async with get_session_factory()() as session:
        logger.info("Starting FRED economic-calendar ingestion...")
        stats = await connector.run(session)
        # BaseConnector.run only flushes — commit or the data is rolled back.
        await session.commit()
        logger.info(f"Economic-calendar ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
