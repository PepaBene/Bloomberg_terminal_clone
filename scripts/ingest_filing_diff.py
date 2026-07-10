"""Ingest section-level filing diffs from SEC EDGAR (Pillar 3, DATA_WIRING_AUDIT §6).

For each entity CIK, discovers its two most recent same-type filings (default 10-K),
diffs them section by section, and loads results into ``filing_sections`` and
``filing_diffs``.

Usage:
    python -m scripts.ingest_filing_diff                     # all CIKs, 10-K
    python -m scripts.ingest_filing_diff --limit 5           # first 5 CIKs
    python -m scripts.ingest_filing_diff --cik 320193        # single CIK (Apple)
    python -m scripts.ingest_filing_diff --filing-type 10-Q
    python -m scripts.ingest_filing_diff --dry-run --limit 1
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_filing_diff import EdgarFilingDiffConnector
from src.models.entity import EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest EDGAR section-level filing diffs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of CIKs")
    parser.add_argument("--cik", type=str, default=None, help="Single CIK to process")
    parser.add_argument("--filing-type", type=str, default="10-K", help="Form type to diff")
    return parser.parse_args()


async def _load_ciks(session, limit: int | None) -> list[str]:
    query = (
        select(EntityIdentifier.identifier_value)
        .where(EntityIdentifier.identifier_type == "CIK")
        .order_by(EntityIdentifier.identifier_value)
    )
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def main() -> None:
    args = parse_args()
    async with get_session_factory()() as session:
        if args.cik:
            ciks = [args.cik]
        else:
            ciks = await _load_ciks(session, args.limit)
        logger.info("Filing-diff ingestion for %d CIK(s), form=%s", len(ciks), args.filing_type)

        connector = EdgarFilingDiffConnector(cik_list=ciks, filing_type=args.filing_type)
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info("Filing-diff ingestion complete: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
