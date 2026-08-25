"""Run the backfill continuously until every company is complete.

Each pass is an isolated subprocess running ``scripts.backfill --all`` for a
bounded number of minutes, so a hang or kill in one pass never takes down the
loop — it just respawns the next pass, which resumes exactly where the last one
left off (progress is tracked in the DB).

This is the "set it and forget it" runner. For true unattended operation across
reboots, schedule ``python -m scripts.backfill --all --max-minutes N`` with the
OS scheduler instead (see BACKFILL.md).

Usage:
    python -m scripts.run_backfill_loop
    python -m scripts.run_backfill_loop --pass-minutes 8 --sleep-seconds 20
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backfill import (  # noqa: E402
    ENTITY_TYPES,
    FILER_TYPES,
    _pending_entities,
    _pending_filers,
    _pending_price_dates,
)
from src.database import get_session_factory  # noqa: E402


async def _remaining(lookback_days: int) -> bool:
    """True if any data type still has un-done subjects."""
    async with get_session_factory()() as session:
        for key in ENTITY_TYPES:
            if await _pending_entities(session, key, 1):
                return True
        for key in FILER_TYPES:
            if await _pending_filers(session, key, 1):
                return True
        if await _pending_price_dates(session, 1, lookback_days):
            return True
    return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Continuous backfill runner")
    p.add_argument("--pass-minutes", type=float, default=8.0,
                   help="Wall-clock budget per backfill pass")
    p.add_argument("--sleep-seconds", type=float, default=20.0,
                   help="Pause between passes (eases DB + rate limits)")
    p.add_argument("--batch-size", type=int, default=25, help="Subjects per batch")
    p.add_argument("--prices-lookback-days", type=int, default=120)
    p.add_argument("--max-passes", type=int, default=0,
                   help="Stop after N passes (0 = until complete)")
    return p.parse_args()


def _remaining_safe(lookback_days: int) -> bool:
    """Completion check that never raises — a transient DB drop must not end the
    loop. Retries a few times; if it still can't tell, assume work remains.

    A single "nothing remaining" result is not trusted on its own: right after
    a pass crashes mid-teardown (e.g. "RuntimeError: Event loop is closed"
    while closing an asyncpg connection), a freshly-opened session can come
    back with a silently-empty/wrong result instead of raising — this once
    caused the loop to declare "Backfill complete" and exit while thousands
    of genuinely-pending ipo/ma_deals/nport/bond_issuances rows sat untouched
    in the DB. Requiring two independent "nothing remaining" reads in a row,
    each on its own fresh connection, makes that false-positive far less
    likely without weakening the retry-on-exception behavior below.
    """
    confirmations = 0
    for attempt in range(4):
        try:
            if asyncio.run(_remaining(lookback_days)):
                return True
            confirmations += 1
            if confirmations >= 2:
                return False
        except Exception as e:  # asyncpg connection drop, etc.
            print(f"  (completion check retry {attempt + 1}: {e})", flush=True)
            confirmations = 0
            time.sleep(5)
    return True  # can't confirm complete → keep going


def main() -> None:
    args = parse_args()
    passes = 0
    while True:
        passes += 1
        print(f"\n=== backfill pass {passes} (up to {args.pass_minutes} min) ===",
              flush=True)
        # A pass or the completion check can crash on a transient DB drop; catch
        # everything so the loop is self-healing and just moves to the next pass.
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "scripts.backfill", "--all",
                    "--max-minutes", str(args.pass_minutes),
                    "--batch-size", str(args.batch_size),
                    "--prices-lookback-days", str(args.prices_lookback_days),
                ],
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            if not _remaining_safe(args.prices_lookback_days):
                print("\nBackfill complete — every company is up to date.", flush=True)
                break
        except Exception as e:
            print(f"pass {passes} errored ({e}); continuing after backoff", flush=True)

        if args.max_passes and passes >= args.max_passes:
            print(f"\nReached --max-passes ({args.max_passes}); stopping.", flush=True)
            break
        time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
