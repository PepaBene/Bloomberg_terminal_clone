"""Ingest US congressional trades (STOCK Act periodic transaction reports).

Pulls free, public House and Senate disclosure feeds and loads them into the
``congressional_trades`` table for the Smart-Money tracker.

Usage:
    python -m scripts.ingest_congress              # both chambers
    python -m scripts.ingest_congress --chamber HOUSE
    python -m scripts.ingest_congress --limit 500
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.congress_trades import CongressTradesConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _run_chamber(chamber: str, limit: int | None) -> None:
    connector = CongressTradesConnector(chamber=chamber)
    async with get_session_factory()() as session:
        logger.info("Ingesting %s STOCK Act trades...", chamber)
        stats = await connector.run(session, limit=limit)
        await session.commit()
        logger.info("%s ingestion complete: %s", chamber, stats)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest congressional STOCK Act trades")
    parser.add_argument("--chamber", choices=["HOUSE", "SENATE", "BOTH"], default="BOTH")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    chambers = ["HOUSE", "SENATE"] if args.chamber == "BOTH" else [args.chamber]
    for chamber in chambers:
        try:
            await _run_chamber(chamber, args.limit)
        except Exception:
            logger.exception("Failed to ingest %s feed", chamber)


if __name__ == "__main__":
    asyncio.run(main())
