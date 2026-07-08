"""Ingest macroeconomic data from FRED API."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.fred_macro import FredMacroConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = FredMacroConnector()
    async with get_session_factory()() as session:
        logger.info("Starting FRED macroeconomic data ingestion...")
        stats = await connector.run(session)
        # BaseConnector.run only flushes — commit or the data is rolled back.
        await session.commit()
        logger.info(f"FRED ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
