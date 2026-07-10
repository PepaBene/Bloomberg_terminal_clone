"""Ingest recent geopolitical events from GDELT 2.0 (keyless).

Populates ``geopolitical_events`` with news-derived events across a set of
topic buckets (military conflict, sanctions, trade war, coup, election,
terrorism). Severity is derived from the topic bucket; per-article tone is not
available in GDELT's artlist mode.

Usage:
    python -m scripts.ingest_geopolitical
    python -m scripts.ingest_geopolitical --timespan 7d --max-per-topic 15
    python -m scripts.ingest_geopolitical --topics SANCTIONS,TRADE_WAR
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.gdelt_geopolitical import GdeltGeopoliticalConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest GDELT geopolitical events")
    parser.add_argument("--topics", type=str, default=None,
                        help="Comma-separated topic buckets (default: all)")
    parser.add_argument("--timespan", type=str, default="3d")
    parser.add_argument("--max-per-topic", type=int, default=10)
    args = parser.parse_args()

    topics = args.topics.split(",") if args.topics else None
    connector = GdeltGeopoliticalConnector(
        topics=topics, timespan=args.timespan, max_per_topic=args.max_per_topic
    )
    async with get_session_factory()() as session:
        logger.info("Starting GDELT geopolitical events ingestion...")
        stats = await connector.run(session)
        # BaseConnector.run only flushes — commit or the data is rolled back.
        await session.commit()
        logger.info("GDELT ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
