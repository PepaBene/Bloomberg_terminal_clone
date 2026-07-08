"""Pillar 2: Analytics batch runner.

Usage:
    python scripts/run_analytics_batch.py --engine e1
    python scripts/run_analytics_batch.py --engine e2_multiples
    python scripts/run_analytics_batch.py --engine e2_wacc
    python scripts/run_analytics_batch.py --engine all
    python scripts/run_analytics_batch.py --engine e1 --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import sys
import time
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure project root is on path
sys.path.insert(0, ".")

from src.database import get_session_factory  # noqa: E402
from src.models.security import Security  # noqa: E402
from src.engines.base import EngineOutput  # noqa: E402
from src.models.analytics import AnalyticsResult  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("analytics_batch")


async def _get_active_security_ids(session: AsyncSession, limit: int | None = None, since: str | None = None) -> list[UUID]:
    """Fetch all active security IDs. If since is provided, only fetch those with updated data."""
    query = select(Security.security_id).where(Security.status == "ACTIVE")
    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            query = query.where(Security.updated_at >= since_dt)
        except ValueError:
            logger.error("Invalid since format. Expected YYYY-MM-DD")
            raise
    if limit:
        query = query.limit(limit)
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def _persist_outputs(session: AsyncSession, outputs: list[EngineOutput]) -> int:
    """Write EngineOutput rows to analytics_results table. Returns row count."""
    if not outputs:
        return 0
    for out in outputs:
        session.add(AnalyticsResult(
            security_id=out.security_id,
            entity_id=out.entity_id,
            engine_id=out.engine_id,
            metric_name=out.metric_name,
            metric_category=out.metric_category,
            value=out.value,
            unit=out.unit,
            period=out.period,
            period_end_date=out.period_end_date,
            as_of_date=out.as_of_date,
            data_quality=out.data_quality,
            inputs=out.inputs,
            calculation_version=out.calculation_version,
        ))
    await session.flush()
    return len(outputs)


async def run_engine(engine_name: str, dry_run: bool = False, limit: int | None = None, since: str | None = None) -> None:
    """Run a specific engine in batch mode."""
    logger.info("Starting analytics batch: engine=%s dry_run=%s limit=%s since=%s", engine_name, dry_run, limit, since)
    start = time.perf_counter()

    async with get_session_factory()() as session:
        security_ids = await _get_active_security_ids(session, limit=limit, since=since)
        logger.info("Found %d active securities", len(security_ids))

        if not security_ids:
            logger.warning("No active securities found. Nothing to compute.")
            return

        engine_map: dict[str, type] = {}

        # Import engines lazily
        if engine_name in ("e1", "all"):
            from src.engines.e1_ttm import TTMEngine
            from src.engines.e1_ratios import RatioEngine
            from src.engines.e1_dupont import DuPontEngine
            engine_map["ttm"] = TTMEngine
            engine_map["ratios"] = RatioEngine
            engine_map["dupont"] = DuPontEngine

        if engine_name in ("e2_multiples", "all"):
            from src.engines.e2_multiples import MultiplesEngine
            engine_map["multiples"] = MultiplesEngine

        if engine_name in ("e2_wacc", "all"):
            from src.engines.e2_wacc import WACCEngine
            engine_map["wacc"] = WACCEngine

        if engine_name in ("e1_trends", "all"):
            from src.engines.e1_trends import TrendEngine
            engine_map["trends"] = TrendEngine

        if engine_name in ("e1_kpis", "all"):
            from src.engines.e1_industry_kpis import IndustryKPIEngine
            engine_map["industry_kpis"] = IndustryKPIEngine

        if engine_name in ("e3", "all"):
            from src.engines.e3_piotroski import PiotroskiEngine
            from src.engines.e3_altman import AltmanEngine
            from src.engines.e3_beneish import BeneishEngine
            engine_map["piotroski"] = PiotroskiEngine
            engine_map["altman"] = AltmanEngine
            engine_map["beneish"] = BeneishEngine

        total_outputs = 0
        for name, engine_cls in engine_map.items():
            engine = engine_cls()
            logger.info("Running engine: %s (%s)", name, engine.engine_id)
            outputs: list[EngineOutput] = []
            for security_id in security_ids:
                try:
                    result = await asyncio.wait_for(
                        engine.compute(session, security_id=security_id),
                        timeout=30,
                    )
                    outputs.extend(result)
                except asyncio.TimeoutError:
                    logger.warning("Engine %s timed out for security %s after 30s, skipping", name, security_id)
                    continue
                except Exception:
                    logger.exception("Engine %s failed for security %s", name, security_id)
                    continue
            logger.info("  → %d metrics computed", len(outputs))
            total_outputs += len(outputs)

            if not dry_run:
                count = await _persist_outputs(session, outputs)
                logger.info("  → %d rows persisted", count)
                # [Bug 69 fix] Per-engine commits
                await session.commit()

    elapsed = time.perf_counter() - start
    logger.info(
        "Batch complete: %d total metrics in %.1f seconds (%.0f metrics/sec)",
        total_outputs, elapsed, total_outputs / max(elapsed, 0.001),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pillar 2 analytics batch")
    parser.add_argument("--engine", required=True, choices=[
        "e1", "e1_trends", "e1_kpis", "e2_multiples", "e2_wacc", "e3", "all",
    ])
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of securities")
    parser.add_argument("--since", type=str, default=None, help="Only process securities updated since YYYY-MM-DD")
    args = parser.parse_args()

    asyncio.run(run_engine(args.engine, dry_run=args.dry_run, limit=args.limit, since=args.since))


if __name__ == "__main__":
    main()
