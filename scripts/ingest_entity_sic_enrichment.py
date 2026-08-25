"""Enrich entities with SEC EDGAR per-company detail (SIC code, fiscal year
end, incorporation state, address).

EdgarEntityConnector.enrich_with_details() has existed since the entity
connector was written, but nothing ever called it on a resumable, ongoing
basis -- only a one-off `scripts/ingest_edgar.py` run capped at the first 100
entities. Zero of ~8,088 entities have ``primary_sic`` set as a result, which
in turn means nothing downstream that depends on an industry classification
(e.g. the Sector Rankings page) has any input data to work with.

This is naturally resumable with no extra bookkeeping: enrich_with_details()
already selects `WHERE primary_sic IS NULL LIMIT max_entities`, so each call
just picks up the next unenriched batch -- safe to run every lap forever
until it converges (further calls become no-ops once every entity has a
primary_sic).

Usage:
    python -m scripts.ingest_entity_sic_enrichment
    python -m scripts.ingest_entity_sic_enrichment --batch-size 200
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.edgar_entities import EdgarEntityConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest_entity_sic_enrichment")


async def run(batch_size: int) -> None:
    factory = get_session_factory()
    connector = EdgarEntityConnector()
    async with factory() as session:
        stats = await connector.enrich_with_details(session, max_entities=batch_size)
        await session.commit()
        logger.info("SIC enrichment: %s", stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich entities with SEC EDGAR SIC/detail data")
    parser.add_argument("--batch-size", type=int, default=150)
    args = parser.parse_args()
    asyncio.run(run(args.batch_size))


if __name__ == "__main__":
    main()
