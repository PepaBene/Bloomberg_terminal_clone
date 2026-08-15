"""Corporate Action Queue matcher (Pillar 4).

Gap (DEEP_AUDIT_2026-07-16 Dimension 2/3, item 53): ``corporate_action_engine
.match_corporate_actions_to_holdings`` is a correct pure function, but per
its own docstring "has no production caller today" -- nothing ever
populated ``corporate_action_queue``, so ``GET
/v4/portfolios/{id}/corporate-actions`` (src/api/routers/portfolios.py)
returned an empty list forever, even for portfolios holding a security with
a real, already-ingested upcoming dividend or split.

This script joins the security-level ``corporate_actions`` table (which
DOES have a real writer -- scripts/ingest_corporate_actions.py /
src/ingestion/polygon_corporate_actions.py, already scheduled) against
every open position across every portfolio and queues one PENDING
``CorporateActionQueue`` row per (portfolio, position, action) match that
isn't already queued.

Usage:
    python -m scripts.match_corporate_actions
    python -m scripts.match_corporate_actions --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.engines import corporate_action_engine
from src.models.corporate_actions import CorporateAction
from src.models.nav_snapshot import CorporateActionQueue
from src.models.position import Position
from src.models.security import SecurityIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("match_corporate_actions")

# Actions announced up to 30 days ago (may still need applying) through 60
# days out (upcoming, worth surfacing early) are considered "relevant".
LOOKBACK_DAYS = 30
LOOKAHEAD_DAYS = 60


async def _load_open_positions(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(select(Position).where(Position.status == "OPEN"))).scalars().all()
    return [{"id": p.id, "portfolio_id": p.portfolio_id, "ticker": p.ticker} for p in rows]


async def _load_relevant_actions(session: AsyncSession, window_start: date, window_end: date) -> list[dict]:
    rows = (
        await session.execute(
            select(CorporateAction).where(
                CorporateAction.ex_date >= window_start,
                CorporateAction.ex_date <= window_end,
            )
        )
    ).scalars().all()
    if not rows:
        return []

    sec_ids = [r.security_id for r in rows if r.security_id is not None]
    ticker_rows = (
        await session.execute(
            select(SecurityIdentifier.security_id, SecurityIdentifier.identifier_value).where(
                SecurityIdentifier.security_id.in_(sec_ids),
                SecurityIdentifier.identifier_type == "TICKER",
            )
        )
    ).all()
    ticker_by_sec = {sec_id: ticker for sec_id, ticker in ticker_rows}

    actions = []
    for ca in rows:
        ticker = ticker_by_sec.get(ca.security_id)
        if not ticker:
            continue
        actions.append({
            "action_id": ca.action_id,
            "ticker": ticker,
            "action_type": ca.action_type,
            "security_id": ca.security_id,
            "ex_date": ca.ex_date,
            "payment_date": ca.payment_date,
            "status": ca.status,
            "description": ca.description,
        })
    return actions


async def run(dry_run: bool = False) -> int:
    today = date.today()
    window_start = today - timedelta(days=LOOKBACK_DAYS)
    window_end = today + timedelta(days=LOOKAHEAD_DAYS)

    factory = get_session_factory()
    async with factory() as session:
        holdings = await _load_open_positions(session)
        actions = await _load_relevant_actions(session, window_start, window_end)
        logger.info("%d open position(s), %d relevant corporate action(s)", len(holdings), len(actions))

        if not holdings or not actions:
            return 0

        matches = corporate_action_engine.match_corporate_actions_to_holdings(actions, holdings)

        # Dedup against what's already queued for this window -- keyed on
        # the fields that identify "the same action for the same position".
        existing_rows = (
            await session.execute(
                select(
                    CorporateActionQueue.portfolio_id, CorporateActionQueue.position_id,
                    CorporateActionQueue.ex_date, CorporateActionQueue.action_type,
                ).where(CorporateActionQueue.ex_date >= window_start, CorporateActionQueue.ex_date <= window_end)
            )
        ).all()
        existing_keys = {(r[0], r[1], r[2], r[3]) for r in existing_rows}

        queued = 0
        for m in matches:
            action, holding = m["action"], m["holding"]
            key = (holding["portfolio_id"], holding["id"], action["ex_date"], action["action_type"])
            if key in existing_keys:
                continue
            existing_keys.add(key)
            session.add(CorporateActionQueue(
                id=uuid.uuid4(),
                portfolio_id=holding["portfolio_id"],
                position_id=holding["id"],
                action_type=action["action_type"],
                security_id=action["security_id"],
                ticker=action["ticker"],
                ex_date=action["ex_date"],
                payment_date=action["payment_date"],
                details={
                    "description": action.get("description"),
                    "source_status": action.get("status"),
                    "source_action_id": str(action["action_id"]),
                },
                status="PENDING",
            ))
            queued += 1

        if dry_run:
            await session.rollback()
            logger.info("Dry run: %d new queue row(s) would have been created (no commit)", queued)
        else:
            await session.commit()
            logger.info("Queued %d new corporate action(s)", queued)
        return queued


def main() -> None:
    parser = argparse.ArgumentParser(description="Match corporate actions to portfolio holdings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
