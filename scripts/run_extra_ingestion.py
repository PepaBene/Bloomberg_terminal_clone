"""Runner for the standalone ingest_*/compute_*/backfill_* scripts that are
NOT part of scripts/backfill.py's CIK-driven resumable registry.

Four scripts that WERE here (ipo, ma_deals, nport, bond_issuances) have been
migrated into scripts/backfill.py's ENTITY_TYPES registry instead -- they had
the exact same connector_cls(**{kwarg: ciks}, **extra_kwargs) -> connector.run()
shape as everything already there, so they now get real chunked/resumable/
ingestion_progress-tracked treatment (survives a kill, doesn't restart from
scratch) instead of being re-run whole-script on every lap here.

Most of what's left is either a one-shot "fetch a feed and exit" job with no
natural per-company subject to checkpoint against (FRED series, OFAC,
GovInfo, Federal Register, GLEIF, ...) or a pure DB-only computation -- for
these, a whole-script retry on next lap is cheap and proportionate, so
they're just run to completion and retried on failure, not chunked.

ingest_esg_controversies is the one exception: it's per-entity (like the
backfill.py-registry types) but GDELT's rate limiting is severe enough
(~130 entities per 30-minute run, observed live) that restarting from
entity #1 every lap would mean it NEVER reaches entities past the first
~130, forever. PAGINATED_MODULES below gives it a persisted --offset
checkpoint (.cache/extra_ingestion_offsets.json) that advances by
chunk_size each lap and wraps around once it passes the total entity
count, so it eventually cycles through everyone instead of being stuck.

Concurrency: most of these hit a DIFFERENT external API each (FRED, EIA,
World Bank, GDELT, OFAC, Alpha Vantage, Finnhub, ...), so they don't compete
for SEC EDGAR's rate budget the way scripts.backfill's connectors do -- they
run in STAGE_PARALLEL concurrently (bounded) for throughput. The one
remaining SEC-EDGAR-touching script (ingest_relationships) runs alone in its
own stage so it doesn't stack SEC request-rate on top of the backfill loop's
own SEC traffic. Pure-DB compute scripts run last (STAGE_COMPUTE) so they see
whatever landed in the stages before them (e.g. compute_sentiment needs
backfill_news's rows; compute_ownership_summary benefits from
ingest_short_interest having just run).

Each child subprocess gets its own tiny DB pool (DB_POOL_MIN=1/MAX=2) via
explicit env passthrough -- with up to MAX_PARALLEL concurrent children that
caps total extra-ingestion connections at a small, known number regardless of
how many run at once, so this can never repeat the connection-exhaustion
incident from running everything with the default pool_size=10/max_overflow=40.

Usage:
    python -m scripts.run_extra_ingestion
    python -m scripts.run_extra_ingestion --once   # single lap, don't loop
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
MAX_PARALLEL = 6

# Modules that accept --offset/--limit and should page through the full
# entity universe across laps instead of restarting from #1 every time.
# chunk_size is sized to roughly what the module can process before hitting
# its own external rate limit within one lap (see the ingest_esg_controversies
# docstring above -- ~130 entities/30min observed live; 150 gives headroom).
PAGINATED_MODULES: dict[str, dict] = {
    "scripts.ingest_esg_controversies": {"chunk_size": 150},
}
_OFFSET_CHECKPOINT_PATH = REPO_ROOT / ".cache" / "extra_ingestion_offsets.json"


def _load_offsets() -> dict[str, int]:
    try:
        return json.loads(_OFFSET_CHECKPOINT_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_offsets(offsets: dict[str, int]) -> None:
    try:
        _OFFSET_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _OFFSET_CHECKPOINT_PATH.write_text(json.dumps(offsets))
    except OSError:
        pass


async def _total_cik_entities() -> int:
    """Count of entities with a CIK identifier -- the universe PAGINATED_MODULES pages over."""
    from sqlalchemy import func, select
    from src.database import get_session_factory
    from src.models.entity import EntityIdentifier

    async with get_session_factory()() as session:
        return await session.scalar(
            select(func.count()).select_from(EntityIdentifier)
            .where(EntityIdentifier.identifier_type == "CIK")
        ) or 0

# Each child gets a tiny dedicated pool -- these are one-session-at-a-time
# scripts, not the high-concurrency case pool_size=10/max_overflow=40 (the
# global .env default) was sized for. Up to MAX_PARALLEL concurrent children
# * 2 connections each is a small, bounded footprint.
_CHILD_ENV = dict(os.environ)
_CHILD_ENV["DB_POOL_MIN"] = "1"
_CHILD_ENV["DB_POOL_MAX"] = "2"

# -- Stage 1: parallel-safe, each hits its own distinct external API -------
STAGE_PARALLEL: list[str] = [
    # Macro (FRED-based)
    "scripts.ingest_fred",
    "scripts.ingest_central_bank",
    "scripts.ingest_fomc",
    "scripts.ingest_money_market",
    "scripts.ingest_econ_calendar",
    "scripts.ingest_credit_spreads",
    "scripts.ingest_commodities",
    "scripts.ingest_treasury_curve",
    "scripts.ingest_treasury_securities",
    "scripts.ingest_eia_commodity_inventory",
    "scripts.ingest_country_risk",
    # Alt-data / political (all keyless)
    "scripts.ingest_congress",
    "scripts.ingest_geopolitical",
    "scripts.ingest_esg_controversies",
    "scripts.ingest_legislative_bills",
    "scripts.ingest_regulatory_actions",
    "scripts.ingest_sanctions",
    "scripts.ingest_gleif",
    # Estimates / earnings (Alpha Vantage / Finnhub)
    "scripts.ingest_consensus_estimates",
    "scripts.ingest_earnings",
    "scripts.ingest_earnings_surprises",
    # News (sentiment depends on this -- see STAGE_COMPUTE)
    "scripts.backfill_news",
    # Ownership extras
    "scripts.ingest_short_interest",
    "scripts.ingest_openfigi",
]

# -- Stage 2: SEC EDGAR-touching, kept alone so it doesn't stack SEC request
#    rate on top of the concurrently-running scripts.backfill loop ---------
STAGE_SEC: list[str] = [
    "scripts.ingest_relationships",
    # SIC/fiscal-year-end/incorporation-state/address enrichment. Naturally
    # resumable (see the script's docstring) -- shares the same Redis-backed
    # sec_edgar rate limiter as everything else here and in scripts.backfill,
    # so adding it doesn't risk another 429 storm.
    "scripts.ingest_entity_sic_enrichment",
]

# -- Stage 3: pure DB computation, no external API, run last so it sees
#    what landed above (compute_sentiment needs backfill_news's rows) -----
STAGE_COMPUTE: list[str] = [
    "scripts.compute_sentiment",
    "scripts.compute_technicals",
    "scripts.compute_theme_scores",
    "scripts.compute_esg_temperature",
    "scripts.compute_ownership_summary",
    "scripts.compute_shares_outstanding",
    "scripts.compute_debt_maturity",
    # Anomaly detection had zero callers anywhere -- Research > Anomalies
    # could never return data. Idempotent (skips already-recorded
    # entity/type/window rows), so safe to run every lap.
    "scripts.compute_anomalies",
    # Derives entities.gics_sector from primary_sic (see script docstring for
    # why this step was missing) -- must run after ingest_entity_sic_enrichment
    # (stage 2) populates primary_sic, and before compute_industry_profiles
    # below, which requires gics_sector to be set.
    "scripts.assign_gics_from_sic",
    "scripts.compute_industry_profiles",
]


async def run_one(module: str, extra_args: list[str] | None = None) -> int:
    args = extra_args or []
    label = module if not args else f"{module} {' '.join(args)}"
    print(f"\n=== {label} — starting ===", flush=True)
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", module, *args,
            cwd=str(REPO_ROOT),
            env=_CHILD_ENV,
        )
        rc = await asyncio.wait_for(proc.wait(), timeout=1800)  # 30 min ceiling
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass  # process already exited on its own between the timeout firing and kill()
        await proc.wait()
        print(f"=== {label} — TIMED OUT after 30min ===", flush=True)
        return -1
    except Exception as e:
        print(f"=== {label} — errored launching: {e} ===", flush=True)
        return -1
    elapsed = time.monotonic() - start
    print(f"=== {label} — exit {rc} in {elapsed:.1f}s ===", flush=True)
    return rc


def _paginated_args(module: str, offsets: dict[str, int], total: int) -> list[str]:
    """Build --offset/--limit args for a paginated module and advance its checkpoint.

    Mutates `offsets` in place; caller is responsible for persisting it after
    the lap. Advancing regardless of the module's success/failure/timeout is
    deliberate -- a stuck company that always times out shouldn't wedge the
    checkpoint on the same offset forever; better to keep sweeping forward
    and let a later lap's wraparound catch anything missed.
    """
    cfg = PAGINATED_MODULES[module]
    chunk = cfg["chunk_size"]
    offset = offsets.get(module, 0) % max(total, 1)
    offsets[module] = offset + chunk
    return ["--offset", str(offset), "--limit", str(chunk)]


async def run_stage_parallel(modules: list[str]) -> dict[str, int]:
    semaphore = asyncio.Semaphore(MAX_PARALLEL)
    offsets = _load_offsets()
    total = await _total_cik_entities() if any(m in PAGINATED_MODULES for m in modules) else 0

    async def _bounded(m: str) -> int:
        extra = _paginated_args(m, offsets, total) if m in PAGINATED_MODULES else None
        async with semaphore:
            return await run_one(m, extra)

    results = await asyncio.gather(*(_bounded(m) for m in modules))
    if offsets:
        _save_offsets(offsets)
    return dict(zip(modules, results))


async def run_stage_sequential(modules: list[str]) -> dict[str, int]:
    results: dict[str, int] = {}
    offsets = _load_offsets()
    total = await _total_cik_entities() if any(m in PAGINATED_MODULES for m in modules) else 0
    for m in modules:
        extra = _paginated_args(m, offsets, total) if m in PAGINATED_MODULES else None
        results[m] = await run_one(m, extra)
    if offsets:
        _save_offsets(offsets)
    return results


async def run_lap() -> dict[str, int]:
    results: dict[str, int] = {}
    print(f"\n----- stage 1: {len(STAGE_PARALLEL)} modules in parallel (max {MAX_PARALLEL} at once) -----", flush=True)
    results.update(await run_stage_parallel(STAGE_PARALLEL))
    print(f"\n----- stage 2: {len(STAGE_SEC)} SEC EDGAR module(s), sequential -----", flush=True)
    results.update(await run_stage_sequential(STAGE_SEC))
    print(f"\n----- stage 3: {len(STAGE_COMPUTE)} DB-only compute modules, sequential -----", flush=True)
    results.update(await run_stage_sequential(STAGE_COMPUTE))
    return results


async def main_async(once: bool, sleep_seconds: float) -> None:
    lap = 0
    while True:
        lap += 1
        print(f"\n########## lap {lap} ##########", flush=True)
        try:
            results = await run_lap()
            failed = [m for m, rc in results.items() if rc != 0]
            print(f"\nLap {lap} complete: {len(results) - len(failed)}/{len(results)} succeeded.", flush=True)
            if failed:
                print(f"Failed this lap: {failed}", flush=True)
        except Exception as e:
            # A bug in the runner itself (not a child module) must never kill
            # an unattended overnight process -- log and try again next lap.
            # This is exactly how the runner previously died silently for
            # hours: an uncaught ProcessLookupError race in a timeout handler.
            print(f"\nLap {lap} CRASHED: {e!r} -- continuing to next lap", flush=True)
        if once:
            break
        await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the extra (non-backfill-registry) ingestion scripts")
    parser.add_argument("--once", action="store_true", help="Run one lap through the list and exit")
    parser.add_argument("--sleep-seconds", type=float, default=30.0, help="Pause between laps")
    args = parser.parse_args()
    asyncio.run(main_async(args.once, args.sleep_seconds))


if __name__ == "__main__":
    main()
