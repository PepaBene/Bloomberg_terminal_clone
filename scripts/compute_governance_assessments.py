"""Compute and persist governance assessments (Layer 2 §4.7 Pillar-3
follow-through: "Governance | Ingest proxy/board/comp (DEF 14A) + red-flag
text mining -> fills governance_* tables").

Pulls board composition (``board_members``), CEO compensation
(``executive_compensation``), and voting results (``shareholder_proposals``)
per proxy filing (``proxy_filings``, already ingested by
``src/ingestion/edgar_proxy.py``), runs the governance scoring engine
(``src/engines/governance_scoring.py`` -- built, but previously never
called by any ingestion or batch job, confirmed via Phase 2's
infrastructure survey), and persists ``governance_assessments``. Pure
computation + persistence, same pattern as
``scripts/compute_esg_temperature.py``.

NOT derivable from the structured tables ingested today: dual-class share
structure, poison pill provisions, staggered board, majority-voting
bylaws, and related-party transaction flags. These live in DEF 14A prose
(not the tabular sections ``edgar_proxy.py`` parses today), so they're
deliberately left out of the ``governance_data`` dict passed to the
engine rather than guessed -- the engine's own ``.get(key)`` (no default)
already treats an absent key as "no evidence of the negative condition,"
i.e. that red flag is simply never raised until real DEF 14A text-mining
for these five specific provisions is built (a real, scoped follow-up,
not attempted here). The one exception is ``has_majority_voting``, which
the engine itself defaults to raising a flag when absent (see
``detect_red_flags``'s own comment) -- so every assessment computed by
this script will carry a ``no_majority_voting`` flag until that data
exists. That's a correct reflection of "we don't actually know," not a
bug to work around here.

Usage:
    python -m scripts.compute_governance_assessments
    python -m scripts.compute_governance_assessments --limit 50
    python -m scripts.compute_governance_assessments --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import get_session_factory
from src.engines.governance_scoring import compute_governance_score, compute_board_diversity
from src.models.governance_intelligence import (
    BoardMember,
    ExecutiveCompensation,
    GovernanceAssessment,
    ProxyFiling,
    ShareholderProposal,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_governance_assessments")


def _build_governance_data(
    board_members: list[BoardMember], exec_comp: list[ExecutiveCompensation],
) -> dict:
    """Assemble the engine's ``governance_data`` input from one proxy's
    board/comp rows. Only includes keys this data can actually support --
    see module docstring for the five deliberately-omitted structural flags.
    """
    diversity = compute_board_diversity([
        {
            "is_independent": m.is_independent, "is_chair": m.is_chair,
            "tenure_years": m.tenure_years or 0, "age": m.age or 0,
            "gender": m.gender or "M", "expertise_areas": m.expertise_areas or [],
            "other_boards": m.other_boards or [],
        }
        for m in board_members
    ])

    ceo_rows = [e for e in exec_comp if e.role == "CEO"]
    ceo = ceo_rows[0] if ceo_rows else None
    chair_names = {m.person_name for m in board_members if m.is_chair}

    governance_data: dict = {
        "board_independence_pct": diversity["independent_pct"],
        "avg_board_tenure": diversity["avg_tenure"],
    }
    if ceo is not None:
        governance_data["ceo_is_chair"] = ceo.person_name in chair_names
        if ceo.pay_ratio_to_median is not None:
            governance_data["ceo_pay_ratio"] = float(ceo.pay_ratio_to_median)
        if ceo.total_compensation and float(ceo.total_compensation) > 0:
            ltip = float(ceo.stock_awards or 0) + float(ceo.option_awards or 0)
            governance_data["long_term_incentive_pct"] = round(
                ltip / float(ceo.total_compensation) * 100, 2
            )
    return governance_data, diversity


async def _upsert(session, entity_id: UUID, fields: dict) -> None:
    existing = await session.scalar(
        select(GovernanceAssessment).where(
            GovernanceAssessment.entity_id == entity_id,
            GovernanceAssessment.assessment_date == fields["assessment_date"],
        )
    )
    if existing is None:
        session.add(GovernanceAssessment(entity_id=entity_id, **fields))
    else:
        for key, val in fields.items():
            setattr(existing, key, val)


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        query = select(ProxyFiling)
        if limit:
            query = query.limit(limit)
        proxies: list[ProxyFiling] = list((await session.execute(query)).scalars().all())
        logger.info("Computing governance assessments for %d proxy filings", len(proxies))

        if not proxies:
            logger.warning("No proxy_filings found — nothing to compute.")
            return

        computed = 0
        for proxy in proxies:
            board_members = list((
                await session.execute(
                    select(BoardMember).where(BoardMember.proxy_id == proxy.id)
                )
            ).scalars().all())
            exec_comp = list((
                await session.execute(
                    select(ExecutiveCompensation).where(ExecutiveCompensation.proxy_id == proxy.id)
                )
            ).scalars().all())
            proposals = list((
                await session.execute(
                    select(ShareholderProposal).where(ShareholderProposal.proxy_id == proxy.id)
                )
            ).scalars().all())

            if not board_members and not exec_comp:
                continue

            try:
                governance_data, diversity = _build_governance_data(board_members, exec_comp)
                result = compute_governance_score(governance_data)
            except Exception:
                logger.exception("Failed to score governance for proxy %s (entity %s)", proxy.id, proxy.entity_id)
                continue

            fields = {
                "assessment_date": proxy.filing_date,
                "governance_score": result["score"],
                "classification": result["classification"],
                "board_independence_pct": governance_data.get("board_independence_pct"),
                "avg_board_tenure": governance_data.get("avg_board_tenure"),
                "ceo_is_chair": governance_data.get("ceo_is_chair", False),
                "ceo_pay_ratio": governance_data.get("ceo_pay_ratio"),
                "long_term_incentive_pct": governance_data.get("long_term_incentive_pct"),
                "board_diversity_pct": diversity["gender_diversity_pct"],
                "board_interlock_count": diversity["interlock_count"],
                "red_flags": result["red_flags"],
                # Deliberately not set (defaults apply): dual_class,
                # has_poison_pill, has_staggered_board, has_majority_voting,
                # related_party_flag -- see module docstring.
            }
            computed += 1
            if not dry_run:
                await _upsert(session, proxy.entity_id, fields)

            proposal_summary = (
                f", {len(proposals)} shareholder proposal(s)" if proposals else ""
            )
            logger.info(
                "  %s: score=%d (%s), %d red flag(s)%s",
                proxy.entity_id, result["score"], result["classification"],
                len(result["red_flags"]), proposal_summary,
            )

        if not dry_run:
            await session.commit()
        logger.info(
            "Governance assessment run complete: %d assessments %s",
            computed, "computed (dry-run, not persisted)" if dry_run else "persisted",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute governance assessments from proxy data")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of proxy filings")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
