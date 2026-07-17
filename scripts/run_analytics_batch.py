"""Pillar 2: Analytics batch runner — chunked, resumable, idempotent.

Each engine loops over every active security. Some engines (e.g. E2 multiples,
which reads the large eod_prices table per security) take ~0.7s/security, so a
full ``--engine all`` pass is >1 hour of compute — far longer than a single
process reliably lives here. This runner therefore:

  * commits per CHUNK of securities (not once at the very end), so a kill loses
    at most one chunk;
  * records progress per (sub-engine, security) in ``ingestion_progress`` and
    SKIPS already-done pairs, so a re-run resumes instead of restarting;
  * is idempotent — because done pairs are skipped, re-runs never duplicate
    rows (the previous version INSERTed unconditionally and duplicated on every
    run);
  * honors ``--max-minutes`` so it exits cleanly before anything kills it.

Run it repeatedly (or via scripts.run_analytics_loop) and it converges to full
coverage across all engines.

Usage:
    python -m scripts.run_analytics_batch --engine all --max-minutes 12
    python -m scripts.run_analytics_batch --engine e2_multiples
    python -m scripts.run_analytics_batch --status
    python -m scripts.run_analytics_batch --engine all --reset   # clean rebuild
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, ".")

from src.database import get_session_factory  # noqa: E402
from src.models.security import Security  # noqa: E402
from src.engines.base import EngineOutput  # noqa: E402
from src.models.analytics import AnalyticsResult  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("analytics_batch")

CHUNK_SIZE = 200
PER_SECURITY_TIMEOUT = 30

# Sub-engines that make up each --engine selection. Order groups cheap engines
# first so a bounded pass makes visible progress before the slow multiples run.
#
# Dependency ordering for the "all" group (each key's per-security loop runs
# to completion for every active security before the next key starts, so
# ordering here is a real dependency guarantee, not just a suggestion):
#   - "multiples" must precede "comps": comps reads peer securities' own
#     multiples AnalyticsResult rows (via PeerService), so peers need their
#     multiples already computed.
#   - "dcf" and "comps" must precede "football_field": football_field reads
#     the persisted DCFResult/CompsResult rows directly (not a live call),
#     so both must have already run and committed for the subject security.
#   - "wacc" should precede "dcf": DCF loads WACCResult and falls back to a
#     default rate only when missing, so running wacc first gives more
#     securities a real discount rate instead of the fallback.
ENGINE_GROUPS: dict[str, list[str]] = {
    "e1": ["ttm", "ratios", "dupont"],
    "e1_trends": ["trends"],
    "e1_kpis": ["industry_kpis"],
    "e2_multiples": ["multiples"],
    "e2_wacc": ["wacc"],
    "e2_dcf": ["dcf"],
    "e2_comps": ["comps"],
    "e2_football_field": ["football_field"],
    "e3": ["piotroski", "altman", "beneish"],
    "e5_risk": ["risk"],
    "e6": ["flows"],
    "e7_quant": ["quant"],
    "all": ["ttm", "ratios", "dupont", "trends", "industry_kpis",
            "wacc", "piotroski", "altman", "beneish", "multiples",
            "dcf", "comps", "football_field", "risk", "quant", "flows"],
}


def _load_engine(key: str):
    """Lazily import and return the engine class for a sub-engine key."""
    if key == "ttm":
        from src.engines.e1_ttm import TTMEngine
        return TTMEngine
    if key == "ratios":
        from src.engines.e1_ratios import RatioEngine
        return RatioEngine
    if key == "dupont":
        from src.engines.e1_dupont import DuPontEngine
        return DuPontEngine
    if key == "trends":
        from src.engines.e1_trends import TrendEngine
        return TrendEngine
    if key == "industry_kpis":
        from src.engines.e1_industry_kpis import IndustryKPIEngine
        return IndustryKPIEngine
    if key == "multiples":
        from src.engines.e2_multiples import MultiplesEngine
        return MultiplesEngine
    if key == "wacc":
        from src.engines.e2_wacc import WACCEngine
        return WACCEngine
    if key == "dcf":
        from src.engines.e2_dcf import DCFEngine
        return DCFEngine
    if key == "comps":
        from src.engines.e2_comps import CompsEngine
        return CompsEngine
    if key == "football_field":
        from src.engines.e2_football_field import FootballFieldEngine
        return FootballFieldEngine
    if key == "risk":
        from src.engines.e5_risk import RiskEngine
        return RiskEngine
    if key == "quant":
        from src.engines.e7_quant import QuantEngine
        return QuantEngine
    if key == "piotroski":
        from src.engines.e3_piotroski import PiotroskiEngine
        return PiotroskiEngine
    if key == "altman":
        from src.engines.e3_altman import AltmanZScoreEngine
        return AltmanZScoreEngine
    if key == "beneish":
        from src.engines.e3_beneish import BeneishEngine
        return BeneishEngine
    if key == "flows":
        from src.engines.e6_flows import InstitutionalFlowEngine
        return InstitutionalFlowEngine
    raise ValueError(f"unknown engine key: {key}")


def _progress_type(engine_key: str) -> str:
    return f"analytics:{engine_key}"


async def _active_security_ids(session: AsyncSession) -> list[uuid.UUID]:
    result = await session.execute(
        select(Security.security_id).where(Security.status == "ACTIVE")
    )
    return [row[0] for row in result.all()]


async def _done_set(session: AsyncSession, engine_key: str) -> set[str]:
    rows = await session.execute(
        text(
            "SELECT subject_key FROM ingestion_progress "
            "WHERE data_type = :dt AND status = 'SUCCESS'"
        ),
        {"dt": _progress_type(engine_key)},
    )
    return {r[0] for r in rows.all()}


async def _persist_outputs(session: AsyncSession, outputs: list[EngineOutput]) -> int:
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


async def _mark_done(session: AsyncSession, engine_key: str,
                     security_ids: list[uuid.UUID], now: datetime) -> None:
    dt = _progress_type(engine_key)
    for sid in security_ids:
        await session.execute(
            text(
                """
                INSERT INTO ingestion_progress
                    (id, data_type, subject_key, entity_id, status, attempts,
                     last_attempt_at, last_success_at, created_at, updated_at)
                VALUES (:id, :dt, :sk, NULL, 'SUCCESS', 1, :now, :now, :now, :now)
                ON CONFLICT (data_type, subject_key) DO UPDATE SET
                    status = 'SUCCESS', last_success_at = :now, updated_at = :now
                """
            ),
            {"id": uuid.uuid4(), "dt": dt, "sk": str(sid), "now": now},
        )


async def _clear_security_analytics(session: AsyncSession, security_id: uuid.UUID) -> None:
    """Invalidate one security's analytics: drop its results + analytics progress.

    Invalidation is whole-security (all engines at once), which sidesteps the
    fact that several sub-engines share an engine_id (ttm/ratios/dupont are all
    'E1'). After clearing, the normal loop — or recompute_security — regenerates
    every engine for it, so there are never stale or duplicated rows.
    """
    await session.execute(
        text("DELETE FROM analytics_results WHERE security_id = :s"),
        {"s": security_id},
    )
    await session.execute(
        text(
            "DELETE FROM ingestion_progress "
            "WHERE data_type LIKE 'analytics:%' AND subject_key = :s"
        ),
        {"s": str(security_id)},
    )


async def recompute_security(session: AsyncSession, security_id: uuid.UUID) -> int:
    """Recompute ALL engines for a single security, idempotently.

    Used on-demand (e.g. after a company's fundamentals are refreshed) so the
    ratios/valuations/scores reflect the new data immediately. Commits its work.
    """
    await _clear_security_analytics(session, security_id)
    now = datetime.now(timezone.utc)
    total = 0
    for key in ENGINE_GROUPS["all"]:
        engine = _load_engine(key)()
        try:
            outputs = await asyncio.wait_for(
                engine.compute(session, security_id=security_id),
                timeout=PER_SECURITY_TIMEOUT,
            )
        except Exception:
            outputs = []
        await _persist_outputs(session, outputs)
        await _mark_done(session, key, [security_id], now)
        total += len(outputs)
    await session.commit()
    return total


async def reopen_stale_analytics(session: AsyncSession, days: int) -> int:
    """Invalidate analytics for securities not recomputed in ``days`` days.

    A scheduled backstop so every security's analytics is refreshed at least
    every N days, catching new fundamentals/prices even for companies nobody
    viewed. Cleared securities are recomputed by the next batch pass.
    """
    rows = await session.execute(
        text(
            """
            SELECT DISTINCT subject_key FROM ingestion_progress
            WHERE data_type LIKE 'analytics:%'
              AND last_success_at < now() - make_interval(days => :days)
            """
        ),
        {"days": days},
    )
    stale = [r[0] for r in rows.all()]
    for sk in stale:
        await _clear_security_analytics(session, uuid.UUID(sk))
    await session.commit()
    logger.info("Reopened %d stale securities for analytics recompute (>%dd).",
                len(stale), days)
    return len(stale)


async def _reset(session: AsyncSession, engine_keys: list[str]) -> None:
    """Clean-slate rebuild: wipe analytics_results + analytics progress rows.

    Uses TRUNCATE because analytics_results has accumulated duplicates from the
    old INSERT-only runner. Progress is cleared only for the engines in scope.
    """
    await session.execute(text("TRUNCATE TABLE analytics_results"))
    for key in engine_keys:
        await session.execute(
            text("DELETE FROM ingestion_progress WHERE data_type = :dt"),
            {"dt": _progress_type(key)},
        )
    await session.commit()
    logger.info("Reset: truncated analytics_results and cleared progress for %s", engine_keys)


async def run_engine(engine_name: str, *, dry_run: bool = False,
                     max_minutes: float | None = None, reset: bool = False,
                     refresh_days: int = 0) -> None:
    keys = ENGINE_GROUPS[engine_name]
    logger.info("Analytics batch: engine=%s sub-engines=%s dry_run=%s max_minutes=%s",
                engine_name, keys, dry_run, max_minutes)
    start = time.monotonic()
    deadline = start + max_minutes * 60 if max_minutes else None

    async with get_session_factory()() as session:
        if reset and not dry_run:
            await _reset(session, keys)
        if refresh_days > 0 and not dry_run:
            await reopen_stale_analytics(session, refresh_days)

        security_ids = await _active_security_ids(session)
        logger.info("Found %d active securities", len(security_ids))
        if not security_ids:
            logger.warning("No active securities. Nothing to compute.")
            return

        total_outputs = 0
        for key in keys:
            engine = _load_engine(key)()
            done = await _done_set(session, key)
            todo = [sid for sid in security_ids if str(sid) not in done]
            logger.info("engine %s (%s): %d to do, %d already done",
                        key, engine.engine_id, len(todo), len(done))

            for i in range(0, len(todo), CHUNK_SIZE):
                if deadline and time.monotonic() > deadline:
                    logger.info("Time budget reached — stopping cleanly (resumable).")
                    logger.info("Batch chunk done: %d metrics this run.", total_outputs)
                    return
                chunk = todo[i:i + CHUNK_SIZE]
                outputs: list[EngineOutput] = []
                for sid in chunk:
                    try:
                        result = await asyncio.wait_for(
                            engine.compute(session, security_id=sid),
                            timeout=PER_SECURITY_TIMEOUT,
                        )
                        outputs.extend(result)
                    except asyncio.TimeoutError:
                        logger.warning("%s timed out for %s, skipping", key, sid)
                        continue
                    except Exception:
                        logger.exception("%s failed for %s", key, sid)
                        continue

                if not dry_run:
                    # Persist metrics + mark securities done in ONE transaction,
                    # so a kill before commit leaves no half-written state and no
                    # duplicates (the chunk simply reruns next pass).
                    await _persist_outputs(session, outputs)
                    await _mark_done(session, key, chunk, datetime.now(timezone.utc))
                    await session.commit()
                total_outputs += len(outputs)
                logger.info("  %s: chunk %d-%d → %d metrics (running %d)",
                            key, i, i + len(chunk), len(outputs), total_outputs)

    elapsed = time.monotonic() - start
    logger.info("Batch complete: %d metrics in %.1fs (%.0f/sec)",
                total_outputs, elapsed, total_outputs / max(elapsed, 0.001))


async def print_status() -> None:
    async with get_session_factory()() as session:
        total = len(await _active_security_ids(session))
        print(f"\nActive securities: {total}\n")
        print(f"{'sub-engine':16} {'done':>7} {'remaining':>10} {'coverage':>9}")
        print("-" * 46)
        all_done = True
        for key in ENGINE_GROUPS["all"]:
            done = len(await _done_set(session, key))
            remaining = total - done
            if remaining > 0:
                all_done = False
            cov = (done / total * 100) if total else 0
            print(f"{key:16} {done:>7} {remaining:>10} {cov:>8.1f}%")
        rows = await session.scalar(text("SELECT count(*) FROM analytics_results"))
        secs = await session.scalar(text("SELECT count(DISTINCT security_id) FROM analytics_results"))
        print(f"\nanalytics_results rows: {rows}   distinct securities: {secs}")
        print("STATUS: COMPLETE" if all_done else "STATUS: in progress")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pillar 2 analytics batch (resumable)")
    parser.add_argument("--engine", choices=list(ENGINE_GROUPS.keys()))
    parser.add_argument("--status", action="store_true", help="Print coverage and exit")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--max-minutes", type=float, default=None, help="Wall-clock budget")
    parser.add_argument("--reset", action="store_true",
                        help="Truncate analytics_results + clear progress, then recompute")
    parser.add_argument("--refresh-days", type=int, default=0,
                        help="Before running, invalidate analytics for securities "
                             "not recomputed in N days so they get refreshed")
    args = parser.parse_args()

    if args.status or not args.engine:
        asyncio.run(print_status())
        return
    asyncio.run(run_engine(args.engine, dry_run=args.dry_run,
                           max_minutes=args.max_minutes, reset=args.reset,
                           refresh_days=args.refresh_days))


if __name__ == "__main__":
    main()
