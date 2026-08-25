"""Ingest ESG controversies from GDELT (primary) or a configurable JSON feed.

FLAG: The generic-feed fallback path has no default feed URL. Pass
--feed-url or set ESG_CONTROVERSY_FEED_URL to use it instead of GDELT.
Choosing/licensing a paid ESG-controversy source (RepRisk/MSCI/
Sustainalytics) remains an outstanding decision — see the connector module
docstring in src/ingestion/edgar_esg_controversies.py for the full FLAG.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.ingestion.edgar_esg_controversies import EsgControversiesConnector
from src.models.entity import Entity, EntityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest ESG controversies from GDELT (or a configurable feed)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entities to process")
    parser.add_argument(
        "--offset", type=int, default=0,
        help="Skip this many entities (CIK order) before applying --limit -- lets a "
             "caller page through the full universe across repeated invocations, since "
             "GDELT's per-entity query rate makes a single run of the whole universe "
             "impractical (see run_extra_ingestion.py's PAGINATED_MODULES).",
    )
    parser.add_argument("--feed-url", default=None, help="Controversy JSON feed URL (overrides GDELT)")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="GDELT query lookback window in days (default: 90)",
    )
    return parser.parse_args()


async def _load_entities(session, limit: int | None, offset: int = 0) -> list[dict]:
    """Fetch (CIK, legal_name, entity_id) triples to drive the GDELT queries.

    Only entities with a CIK identifier are included. entity_id is passed
    through directly so load() can resolve rows without a redundant lookup.
    """
    query = (
        select(EntityIdentifier.identifier_value, Entity.legal_name, Entity.entity_id)
        .join(Entity, Entity.entity_id == EntityIdentifier.entity_id)
        .where(EntityIdentifier.identifier_type == "CIK")
        .order_by(EntityIdentifier.identifier_value)
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await session.execute(query)
    return [
        {"cik": cik, "legal_name": legal_name, "entity_id": entity_id}
        for cik, legal_name, entity_id in result.all()
    ]


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting ESG controversies ingestion...")

        entities: list[dict] = []
        if not args.feed_url:
            entities = await _load_entities(session, args.limit, args.offset)
            logger.info(f"Loaded {len(entities)} entities (CIK + legal name) from the database.")

        connector = EsgControversiesConnector(
            feed_url=args.feed_url,
            entities=entities,
            gdelt_lookback_days=args.lookback_days,
        )
        if not connector.feed_url and not connector.entities:
            logger.warning("No feed URL and no entities available — nothing to ingest (FLAG).")

        if args.dry_run:
            logger.info("[DRY RUN] No data will be written to the database.")
        stats = await connector.run(session, dry_run=args.dry_run, limit=args.limit)
        if not args.dry_run:
            await session.commit()
        logger.info(f"ESG controversies ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
