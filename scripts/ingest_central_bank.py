"""Ingest central-bank policy decisions derived from FRED series (Pillar 1)."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session_factory
from src.ingestion.central_bank_policy import CentralBankPolicyConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest central-bank policy decisions from FRED policy-rate series"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--start-date", default="2000-01-01", help="FRED observation_start")
    parser.add_argument(
        "--banks",
        default=None,
        help="Comma-separated bank_code:fred_series pairs (default: FED/ECB/BOE)",
    )
    return parser.parse_args()


def _parse_banks(spec: str | None) -> dict[str, str] | None:
    if not spec:
        return None
    banks: dict[str, str] = {}
    for pair in spec.split(","):
        if ":" in pair:
            code, series = pair.split(":", 1)
            banks[code.strip().upper()] = series.strip()
    return banks or None


async def main():
    args = parse_args()
    async with get_session_factory()() as session:
        logger.info("Starting central-bank policy (FRED) ingestion...")
        connector = CentralBankPolicyConnector(
            banks=_parse_banks(args.banks), start_date=args.start_date
        )
        stats = await connector.run(session, dry_run=args.dry_run)
        if not args.dry_run:
            await session.commit()
        logger.info(f"Central-bank policy ingestion complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
