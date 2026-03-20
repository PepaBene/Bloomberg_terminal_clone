"""SLA monitoring for batch jobs.

Tracks start/end times of ingestion jobs and alerts (via logging) when a
job exceeds its configured SLA.
"""

import logging
import time
from datetime import datetime, timezone

from src.scheduler.batch_config import BATCH_JOBS_BY_NAME, BatchJob

logger = logging.getLogger(__name__)

# In-memory tracking (swap for Redis/DB in production)
_job_runs: dict[str, dict] = {}


def record_job_start(job_name: str) -> None:
    """Record that a batch job has started."""
    _job_runs[job_name] = {
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "status": "RUNNING",
    }
    logger.info("Job '%s' started at %s", job_name, _job_runs[job_name]["started_at"].isoformat())


def record_job_end(job_name: str, *, success: bool = True) -> None:
    """Record that a batch job has completed and check SLA."""
    run = _job_runs.get(job_name)
    if not run:
        logger.warning("No start record for job '%s'; cannot measure SLA.", job_name)
        return

    run["finished_at"] = datetime.now(timezone.utc)
    run["status"] = "SUCCESS" if success else "FAILED"

    elapsed_seconds = (run["finished_at"] - run["started_at"]).total_seconds()
    elapsed_minutes = elapsed_seconds / 60

    job_spec = BATCH_JOBS_BY_NAME.get(job_name)
    if job_spec and elapsed_minutes > job_spec.sla_minutes:
        logger.error(
            "SLA BREACH: Job '%s' took %.1f min (SLA: %d min)",
            job_name,
            elapsed_minutes,
            job_spec.sla_minutes,
        )
    else:
        logger.info(
            "Job '%s' completed in %.1f min (status=%s)",
            job_name,
            elapsed_minutes,
            run["status"],
        )


def get_job_status(job_name: str) -> dict | None:
    """Return the latest run info for a job, or None."""
    return _job_runs.get(job_name)


def get_all_statuses() -> dict[str, dict]:
    """Return status of all tracked jobs."""
    return dict(_job_runs)
