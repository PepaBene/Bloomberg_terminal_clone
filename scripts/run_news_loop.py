"""Run the news backfill continuously until every entity is complete.

Each pass is an isolated subprocess running ``scripts.backfill_news`` for a
bounded number of minutes, so a hang or kill in one pass never takes down the
loop — it just respawns the next pass, which resumes exactly where the last one
left off (progress is tracked in ``ingestion_progress``).

Usage:
    python -m scripts.run_news_loop
    python -m scripts.run_news_loop --pass-minutes 8 --sleep-seconds 20 --days 30
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backfill_news import _pending  # noqa: E402
from src.database import get_session_factory  # noqa: E402


async def _remaining() -> bool:
    """True if any entity still has un-done news."""
    async with get_session_factory()() as session:
        return bool(await _pending(session, 1))


def _remaining_safe() -> bool:
    """Completion check that never raises — a transient DB drop must not end the
    loop. Retries a few times; if it still can't tell, assume work remains."""
    for attempt in range(3):
        try:
            return asyncio.run(_remaining())
        except Exception as e:  # asyncpg connection drop, etc.
            print(f"  (completion check retry {attempt + 1}: {e})", flush=True)
            time.sleep(5)
    return True  # can't confirm complete → keep going


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Continuous news backfill runner")
    p.add_argument("--pass-minutes", type=float, default=8.0,
                   help="Wall-clock budget per pass")
    p.add_argument("--sleep-seconds", type=float, default=20.0,
                   help="Pause between passes (eases DB + rate limits)")
    p.add_argument("--batch-size", type=int, default=20, help="Entities per batch")
    p.add_argument("--days", type=int, default=30,
                   help="Look-back window of news to fetch per entity")
    p.add_argument("--max-passes", type=int, default=0,
                   help="Stop after N passes (0 = until complete)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    passes = 0
    while True:
        passes += 1
        print(f"\n=== news backfill pass {passes} (up to {args.pass_minutes} min) ===",
              flush=True)
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "scripts.backfill_news",
                    "--max-minutes", str(args.pass_minutes),
                    "--batch-size", str(args.batch_size),
                    "--days", str(args.days),
                ],
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            if not _remaining_safe():
                print("\nNews backfill complete — every entity is up to date.",
                      flush=True)
                break
        except Exception as e:
            print(f"pass {passes} errored ({e}); continuing after backoff", flush=True)

        if args.max_passes and passes >= args.max_passes:
            print(f"\nReached --max-passes ({args.max_passes}); stopping.", flush=True)
            break
        time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
