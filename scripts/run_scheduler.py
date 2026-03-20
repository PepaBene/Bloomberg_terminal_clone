"""Simple batch scheduler for Bloomberg Data Fabric ingestion jobs.

Uses APScheduler (if installed) or prints crontab entries for production.

Usage:
    python scripts/run_scheduler.py                # Run interactive scheduler
    python scripts/run_scheduler.py --validate     # Validate all schedules
    python scripts/run_scheduler.py --crontab      # Print crontab entries
"""

import argparse
import asyncio
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.scheduler.batch_config import BATCH_JOBS


def validate_schedules() -> bool:
    """Validate that all batch job configurations are correct."""
    errors = []
    for job in BATCH_JOBS:
        script_path = PROJECT_ROOT / job.script
        if not script_path.exists():
            errors.append(f"  {job.name}: script not found -> {job.script}")
        parts = job.cron.split()
        if len(parts) != 5:
            errors.append(f"  {job.name}: invalid cron expression '{job.cron}' (need 5 fields)")
        if job.sla_minutes <= 0:
            errors.append(f"  {job.name}: SLA must be positive, got {job.sla_minutes}")

    if errors:
        logger.error("Validation FAILED:\n%s", "\n".join(errors))
        return False

    logger.info("All %d batch jobs validated successfully.", len(BATCH_JOBS))
    for job in BATCH_JOBS:
        logger.info("  %-30s  cron=%-20s  sla=%dmin  [%s]", job.name, job.cron, job.sla_minutes, job.domain)
    return True


def print_crontab() -> None:
    """Print crontab entries for all batch jobs."""
    python = sys.executable
    print("# Bloomberg Data Fabric — Batch Schedule")
    print(f"# Generated from {__file__}")
    print()
    for job in BATCH_JOBS:
        script = PROJECT_ROOT / job.script
        print(f"# {job.description}")
        print(f"{job.cron}  {python} {script}")
        print()


def run_scheduler() -> None:
    """Run the interactive scheduler using APScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error(
            "APScheduler not installed. Install with: pip install apscheduler\n"
            "Or use --crontab to generate cron entries."
        )
        sys.exit(1)

    scheduler = BlockingScheduler()

    for job in BATCH_JOBS:
        parts = job.cron.split()
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        def _run_script(script_path=str(PROJECT_ROOT / job.script), name=job.name):
            logger.info("Starting job: %s", name)
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Job '%s' completed successfully.", name)
            else:
                logger.error("Job '%s' FAILED (rc=%d): %s", name, result.returncode, result.stderr[:500])

        scheduler.add_job(_run_script, trigger, id=job.name, name=job.name)
        logger.info("Scheduled: %s (%s)", job.name, job.cron)

    logger.info("Scheduler started with %d jobs. Press Ctrl+C to stop.", len(BATCH_JOBS))
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


def main():
    parser = argparse.ArgumentParser(description="Bloomberg Data Fabric batch scheduler")
    parser.add_argument("--validate", action="store_true", help="Validate all job configs")
    parser.add_argument("--crontab", action="store_true", help="Print crontab entries")
    args = parser.parse_args()

    if args.validate:
        ok = validate_schedules()
        sys.exit(0 if ok else 1)
    elif args.crontab:
        print_crontab()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
