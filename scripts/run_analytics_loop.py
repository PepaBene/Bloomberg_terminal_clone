"""Run the analytics batch continuously until every engine is complete.

Each pass is an isolated subprocess running ``scripts.run_analytics_batch
--engine all`` for a bounded number of minutes. Because the batch is resumable
(progress per sub-engine/security in ingestion_progress) and self-healing here,
a hang or kill in one pass never loses committed work — the next pass resumes.

Usage:
    python -m scripts.run_analytics_loop
    python -m scripts.run_analytics_loop --pass-minutes 12 --sleep-seconds 15
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_analytics_batch import (  # noqa: E402
    ENGINE_GROUPS,
    _active_security_ids,
    _done_set,
)
from src.database import get_session_factory  # noqa: E402


async def _remaining() -> int:
    """Total (sub-engine, security) pairs still to compute across all engines."""
    async with get_session_factory()() as session:
        total = len(await _active_security_ids(session))
        remaining = 0
        for key in ENGINE_GROUPS["all"]:
            remaining += total - len(await _done_set(session, key))
        return remaining


def _remaining_safe() -> int:
    for attempt in range(3):
        try:
            return asyncio.run(_remaining())
        except Exception as e:
            print(f"  (remaining check retry {attempt + 1}: {e})", flush=True)
            time.sleep(5)
    return 1  # can't confirm done → keep going


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Continuous analytics runner")
    p.add_argument("--pass-minutes", type=float, default=12.0)
    p.add_argument("--sleep-seconds", type=float, default=15.0)
    p.add_argument("--max-passes", type=int, default=0, help="0 = until complete")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    passes = 0
    while True:
        passes += 1
        remaining = _remaining_safe()
        print(f"\n=== analytics pass {passes} ({remaining} pairs remaining, "
              f"up to {args.pass_minutes} min) ===", flush=True)
        if remaining == 0:
            print("\nAnalytics complete — every engine computed for every security.",
                  flush=True)
            break
        try:
            subprocess.run(
                [sys.executable, "-m", "scripts.run_analytics_batch",
                 "--engine", "all", "--max-minutes", str(args.pass_minutes)],
                cwd=str(Path(__file__).resolve().parent.parent),
            )
        except Exception as e:
            print(f"pass {passes} errored ({e}); continuing after backoff", flush=True)

        if args.max_passes and passes >= args.max_passes:
            print(f"\nReached --max-passes ({args.max_passes}); stopping.", flush=True)
            break
        time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
