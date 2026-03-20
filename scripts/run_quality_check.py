"""Run data quality checks across all domains."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.quality.scoring import run_quality_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    async with get_session_factory()() as session:
        logger.info("Running data quality checks...")
        scores = await run_quality_check(session)
        await session.commit()

        logger.info("\nQuality Scores:")
        for score in scores:
            logger.info(
                f"  {score.domain}: overall={score.overall_score}, "
                f"completeness={score.completeness_score}, "
                f"accuracy={score.accuracy_score}, "
                f"issues={score.issues_count}, "
                f"critical={score.critical_issues}"
            )


if __name__ == "__main__":
    asyncio.run(main())
