"""Compute real macro theme-exposure scores for the whole entity universe.

Populates ``macro_theme_scores``, which previously had zero producers
anywhere in the codebase (see DATA_WIRING_AUDIT.md §6) -- the read
endpoints under `/v4/research/themes/*` were query-complete but always
empty. This reuses ``macro_scenario_engine.compute_theme_exposures()``,
which is built on the same tested ``SECTOR_SENSITIVITIES``/
``estimate_eps_impact()`` formula the scenario-run endpoint already uses,
applied as 4 standardized single-factor macro shocks (GDP growth,
inflation, rate hikes, oil prices) instead of a named composite scenario.
Pure local computation -- no external API calls, safe to run as often as
fundamentals/sectors change.

Usage:
    python -m scripts.compute_theme_scores
    python -m scripts.compute_theme_scores --limit 200
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from src.database import get_session_factory  # noqa: E402
from src.models.entity import Entity  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    # Imported lazily so this script and the router share one implementation
    # (research_themes.py) instead of a second copy of the compute logic.
    from src.api.routers.research_themes import _compute_theme_scores_for_entity

    parser = argparse.ArgumentParser(description="Compute macro theme-exposure scores")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of entities processed")
    args = parser.parse_args()

    async with get_session_factory()() as session:
        stmt = select(Entity.entity_id, Entity.gics_sector).where(Entity.gics_sector.isnot(None))
        if args.limit:
            stmt = stmt.limit(args.limit)
        entities = (await session.execute(stmt)).all()

        scored = skipped = 0
        for entity_id, gics_sector in entities:
            if await _compute_theme_scores_for_entity(session, entity_id, gics_sector):
                scored += 1
            else:
                skipped += 1

        await session.commit()
        logger.info(
            "Theme scores computed for %d entities (%d skipped, no mapped GICS sector)",
            scored, skipped,
        )


if __name__ == "__main__":
    asyncio.run(main())
