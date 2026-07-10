"""Ingest SEC EDGAR Form 4 insider transactions (Pillar 3).

Drives EdgarForm4Connector against issuer CIKs from entity_identifiers,
writing insider_holdings, insider_transactions_p3 and insider_signals.
Commits after ingestion. Use --limit / --ciks for small, targeted runs.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_form4 import EdgarForm4Connector
from src.models.entity import EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest SEC EDGAR Form 4 insider transactions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entity CIKs to process")
    parser.add_argument("--ciks", type=str, default=None, help="Comma-separated issuer CIKs (overrides DB lookup)")
    parser.add_argument("--days-back", type=int, default=30, help="Days of Form 4 history to look back")
    parser.add_argument("--max-filings", type=int, default=50, help="Max Form 4 filings per issuer")
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
        if args.ciks:
            ciks = [c.strip() for c in args.ciks.split(",") if c.strip()]
        else:
            ciks = await _load_ciks(session, args.limit)
        logger.info(f"Driving Form 4 ingestion for {len(ciks)} issuer CIKs.")

        connector = EdgarForm4Connector(
            issuer_ciks=ciks,
            days_back=args.days_back,
            max_filings_per_cik=args.max_filings,
        )
        stats = await connector.run(session, dry_run=args.dry_run, limit=None)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Form 4 ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
