"""Ingest securities from OpenFIGI."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.openfigi_securities import OpenFigiSecurityConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    connector = OpenFigiSecurityConnector()
    async with get_session_factory()() as session:
        logger.info("Starting OpenFIGI security ingestion...")
        stats = await connector.run(session)
        await session.commit()
        logger.info(f"OpenFIGI ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
