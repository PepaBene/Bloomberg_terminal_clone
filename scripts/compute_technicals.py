"""Compute and persist technical indicator values (Spec — Pillar 1 P5).

Loads EODPrice history per security, runs the technical_studies engine, and
persists the latest value of each indicator into ``technical_study_values``.
The indicator math itself is unchanged — this only wires compute -> persist.

Usage:
    python -m scripts.compute_technicals
    python -m scripts.compute_technicals --limit 50
    python -m scripts.compute_technicals --dry-run
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
from src.engines.technical_studies import latest_study_values
from src.models.security import EODPrice, Security
from src.models.technical_studies import TechnicalStudyValue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_technicals")


async def _load_prices(session, security_id: UUID):
    """Return (dates, highs, lows, closes, volumes) ordered oldest-first."""
    rows = (
        await session.execute(
            select(
                EODPrice.price_date,
                EODPrice.high,
                EODPrice.low,
                EODPrice.close,
                EODPrice.volume,
            )
            .where(EODPrice.security_id == security_id)
            .order_by(EODPrice.price_date.asc())
        )
    ).all()

    dates, highs, lows, closes, volumes = [], [], [], [], []
    for price_date, high, low, close, volume in rows:
        if close is None:
            continue
        c = float(close)
        dates.append(price_date)
        closes.append(c)
        # Fall back to close when OHLC components are missing.
        highs.append(float(high) if high is not None else c)
        lows.append(float(low) if low is not None else c)
        volumes.append(float(volume) if volume is not None else 0.0)
    return dates, highs, lows, closes, volumes


async def _persist(session, security_id: UUID, study_date, values: list[dict]) -> int:
    count = 0
    for v in values:
        existing = await session.scalar(
            select(TechnicalStudyValue).where(
                TechnicalStudyValue.security_id == security_id,
                TechnicalStudyValue.study_date == study_date,
                TechnicalStudyValue.indicator == v["indicator"],
            )
        )
        if existing is None:
            session.add(
                TechnicalStudyValue(
                    security_id=security_id,
                    study_date=study_date,
                    indicator=v["indicator"],
                    value=v["value"],
                    category=v["category"],
                )
            )
        else:
            existing.value = v["value"]
            existing.category = v["category"]
        count += 1
    return count


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Security.security_id).where(Security.status == "ACTIVE")
        if limit:
            query = query.limit(limit)
        security_ids: list[UUID] = [row[0] for row in (await session.execute(query)).all()]
        logger.info("Computing technical studies for %d securities", len(security_ids))

        if not security_ids:
            logger.warning("No active securities found — nothing to compute.")
            return

        total_rows = 0
        for security_id in security_ids:
            try:
                dates, highs, lows, closes, volumes = await _load_prices(session, security_id)
                if not closes:
                    continue
                values = latest_study_values(highs, lows, closes, volumes)
                if not values:
                    continue
                if not dry_run:
                    total_rows += await _persist(session, security_id, dates[-1], values)
                else:
                    total_rows += len(values)
            except Exception:
                logger.exception("Failed to compute technicals for %s", security_id)
                continue

        if not dry_run:
            await session.commit()
        logger.info(
            "Technical studies run complete: %d indicator rows %s",
            total_rows,
            "computed (dry-run, not persisted)" if dry_run else "persisted",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute technical study values")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of securities")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
