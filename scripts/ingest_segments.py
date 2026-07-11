"""Ingest business-segment data from SEC EDGAR XBRL company facts (Domain 3).

Drives ``EdgarSegmentsConnector`` across the entity CIK list, following the
same CIK-list-driven pattern as ``ingest_capital_structure.py`` /
``ingest_corporate_actions.py``. Populates ``SegmentData`` rows, which back
the ``/segments?segment_type=GEOGRAPHIC`` (and ``BUSINESS``) endpoints.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_segments import EdgarSegmentsConnector
from src.models.entity import EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest business-segment data from SEC EDGAR XBRL company facts"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of CIKs to process")
    return parser.parse_args()


async def _load_ciks(session, limit: int | None) -> list[str]:
    """Fetch entity CIK numbers to drive the connector, respecting --limit."""
    query = (
        select(EntityIdentifier.identifier_value)
        .where(EntityIdentifier.identifier_type == "CIK")
        .order_by(EntityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting EDGAR segments ingestion...")
        ciks = await _load_ciks(session, args.limit)
        logger.info(f"Loaded {len(ciks)} entity CIKs from the database.")
        connector = EdgarSegmentsConnector(ciks=ciks)
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Segments ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
