"""Derive entities.gics_sector/gics_industry_group/gics_industry from
entities.primary_sic via the sic_to_gics_mapping crosswalk.

Every piece needed for the Sector Rankings page already existed --
entity_sic_enrichment populates primary_sic, sic_to_gics_mapping.json seeds a
real 66-row SIC->GICS crosswalk, gics_classifications has the full GICS tree,
and compute_industry_profiles.py rolls entities up by gics_sector -- but
nothing ever ran the middle step of actually setting entities.gics_sector
from primary_sic. compute_industry_profiles.py's `WHERE e.gics_sector IS NOT
NULL` filter silently matched zero entities as a result.

Naturally resumable: only touches entities with primary_sic set and
gics_sector still NULL, so re-running just picks up newly-enriched entities.

Usage:
    python -m scripts.assign_gics_from_sic
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("assign_gics_from_sic")

_SQL = text(
    """
    UPDATE entities e
    SET
        gics_sector = gc.sector_code,
        gics_industry_group = gc.industry_group_code,
        gics_industry = gc.industry_code
    FROM sic_to_gics_mapping m
    JOIN gics_classifications gc ON gc.sub_industry_code = m.gics_sub_industry_code
    WHERE e.primary_sic = m.sic_code
      AND e.primary_sic IS NOT NULL
      AND e.gics_sector IS NULL
    """
)


async def run() -> None:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(_SQL)
        await session.commit()
        logger.info("Assigned GICS classification to %d entities", result.rowcount)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
