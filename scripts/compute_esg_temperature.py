"""Compute and persist ESG implied-temperature scores (Spec — Pillar 1 P5).

Pulls emissions data from ``esg_metrics`` per entity, runs the Paris-alignment
scoring engine, and persists ``esg_temperature_scores``. Pure computation.

NOTE: ESG ingestion in this codebase is currently governance-only, so
``esg_metrics`` typically holds no emissions rows. This script wires the full
compute+persist path and degrades cleanly — entities without emissions inputs
are skipped and it will simply persist nothing until emissions data exists.

Usage:
    python -m scripts.compute_esg_temperature
    python -m scripts.compute_esg_temperature --limit 50
    python -m scripts.compute_esg_temperature --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.engines.esg_temperature import summarize_entity_emissions
from src.models.esg import ESGMetric
from src.models.esg_temperature import ESGTemperatureScore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_esg_temperature")


async def _upsert(session, entity_id: UUID, fields: dict) -> None:
    existing = await session.scalar(
        select(ESGTemperatureScore).where(
            ESGTemperatureScore.entity_id == entity_id,
            ESGTemperatureScore.as_of_date == fields["as_of_date"],
        )
    )
    if existing is None:
        session.add(ESGTemperatureScore(entity_id=entity_id, **fields))
    else:
        for key, val in fields.items():
            setattr(existing, key, val)


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        query = select(ESGMetric.entity_id).distinct()
        if limit:
            query = query.limit(limit)
        entity_ids: list[UUID] = [row[0] for row in (await session.execute(query)).all()]
        logger.info("Computing ESG temperature for %d entities with ESG metrics", len(entity_ids))

        if not entity_ids:
            logger.warning(
                "No entities with ESG metrics found — nothing to compute "
                "(emissions data may not be ingested yet)."
            )
            return

        computed = 0
        for entity_id in entity_ids:
            rows = (
                await session.execute(
                    select(
                        ESGMetric.metric_type,
                        ESGMetric.period_end_date,
                        ESGMetric.value,
                    ).where(ESGMetric.entity_id == entity_id)
                )
            ).all()
            metric_rows = [
                {"metric_type": mt, "period_end_date": ped, "value": val}
                for mt, ped, val in rows
            ]
            try:
                fields = summarize_entity_emissions(metric_rows)
            except Exception:
                logger.exception("Failed to score ESG temperature for %s", entity_id)
                continue
            if fields is None:
                continue
            computed += 1
            if not dry_run:
                await _upsert(session, entity_id, fields)

        if not dry_run:
            await session.commit()
        logger.info(
            "ESG temperature run complete: %d scores %s",
            computed,
            "computed (dry-run, not persisted)" if dry_run else "persisted",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute ESG implied-temperature scores")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entities")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
