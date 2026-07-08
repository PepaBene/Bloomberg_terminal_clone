"""Ingest business relationships from SEC EDGAR 10-K NLP analysis (Domain 10)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_10k_nlp import Edgar10KNLPConnector
from src.models.entity import Entity, EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest business relationships from EDGAR 10-K NLP")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of filings to process")
    return parser.parse_args()


async def _load_ciks_and_names(session, limit: int | None):
    """Return (cik_list, known_entity_names) for the 10-K NLP connector.

    ``cik_list`` (limited by --limit) drives which filings are processed;
    ``known_entity_names`` is the full entity dictionary used to match
    customer/supplier/competitor mentions in the filing text.
    """
    rows = (
        await session.execute(
            select(
                EntityIdentifier.identifier_value,
                EntityIdentifier.entity_id,
                Entity.legal_name,
            )
            .join(Entity, Entity.entity_id == EntityIdentifier.entity_id)
            .where(EntityIdentifier.identifier_type == "CIK")
            .order_by(Entity.legal_name)
        )
    ).all()

    known_entity_names = [
        {"entity_id": r.entity_id, "name": r.legal_name} for r in rows
    ]
    ciks = [r.identifier_value for r in rows]
    if limit is not None:
        ciks = ciks[:limit]
    return ciks, known_entity_names


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting EDGAR 10-K NLP relationship extraction...")
        ciks, known_entity_names = await _load_ciks_and_names(session, args.limit)
        logger.info(
            f"Loaded {len(ciks)} entity CIKs and {len(known_entity_names)} "
            f"known entity names from the database."
        )
        connector = Edgar10KNLPConnector(
            cik_list=ciks, known_entity_names=known_entity_names
        )
        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Relationship extraction complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
