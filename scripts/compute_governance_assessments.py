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

Dual-class share structure, poison pill provisions, staggered board,
majority-voting bylaws, and related-party transaction flags live in DEF
14A prose, not the tabular sections ``edgar_proxy.py``'s board/comp/
proposal parsers cover -- that used to mean this script left all five
keys out of ``governance_data`` entirely. It now mines them from the
proxy's own body text via ``src/ingestion/proxy_red_flags.py`` (opt-out
via ``--no-mine-red-flags``; on by default, matching this codebase's
"opt into the one piece of network I/O at the production entry point"
convention -- see ``news_enrichment.py::enrich_new_articles``). Mining is
best-effort text search, same honesty contract as everywhere else in
this codebase: a key is only ever set to a value ``detect_red_flags``
was actually given evidence for; an unmined or ambiguous proxy simply
carries no evidence for that flag, which is what the engine's own
``.get(key)`` semantics already handle correctly (except
``has_majority_voting``, which the engine itself defaults to raising a
flag for when absent -- see ``detect_red_flags``'s own comment -- so an
un-mined proxy still produces a *correct*, not fabricated, result there).

Usage:
    python -m scripts.compute_governance_assessments
    python -m scripts.compute_governance_assessments --limit 50
    python -m scripts.compute_governance_assessments --dry-run
    python -m scripts.compute_governance_assessments --no-mine-red-flags
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
from src.ingestion.edgar_proxy import EdgarProxyConnector, _strip_tags
from src.ingestion.proxy_red_flags import mine_structural_red_flags
from src.models.governance_intelligence import (
    BoardMember,
    ExecutiveCompensation,
    GovernanceAssessment,
    ProxyFiling,
    ShareholderProposal,
)

# The five structural red-flag keys DEF 14A text-mining can populate --
# only ever included in the persisted `fields` dict when actually mined
# with a definite answer (see module docstring); an un-mined proxy leaves
# these columns at whatever they already were (upsert) or the model's own
# default (a brand-new row).
_STRUCTURAL_FLAG_KEYS = (
    "dual_class", "has_poison_pill", "has_staggered_board",
    "has_majority_voting", "related_party_flag",
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


async def _mine_red_flags_for_proxy(connector: EdgarProxyConnector, proxy: ProxyFiling) -> dict:
    """Fetch one proxy's raw body (reusing the connector's own rate-limited
    SEC fetch) and mine the five structural red flags from it. Returns
    ``{}`` -- not a guess -- on any failure: no ``filing_url``, a failed
    fetch, or no definite pattern match in the text.
    """
    if not proxy.filing_url:
        return {}
    html = await connector._fetch_body(proxy.filing_url)
    if not html:
        return {}
    return mine_structural_red_flags(_strip_tags(html))


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


async def run(dry_run: bool = False, limit: int | None = None, mine_red_flags: bool = True) -> None:
    factory = get_session_factory()
    connector = EdgarProxyConnector(parse_bodies=False) if mine_red_flags else None
    try:
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
                    if connector is not None:
                        governance_data.update(await _mine_red_flags_for_proxy(connector, proxy))
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
                }
                # Only set a structural flag column when text-mining (or
                # some future source) actually produced evidence for it --
                # an un-mined run leaves an existing row's value alone
                # (upsert) or the model's own default (a new row), never a
                # guessed literal here.
                for key in _STRUCTURAL_FLAG_KEYS:
                    if key in governance_data:
                        fields[key] = governance_data[key]

                computed += 1
                if not dry_run:
                    await _upsert(session, proxy.entity_id, fields)

                mined_flags = [k for k in _STRUCTURAL_FLAG_KEYS if k in governance_data]
                proposal_summary = (
                    f", {len(proposals)} shareholder proposal(s)" if proposals else ""
                )
                mined_summary = f", mined {mined_flags}" if mined_flags else ""
                logger.info(
                    "  %s: score=%d (%s), %d red flag(s)%s%s",
                    proxy.entity_id, result["score"], result["classification"],
                    len(result["red_flags"]), proposal_summary, mined_summary,
                )

            if not dry_run:
                await session.commit()
            logger.info(
                "Governance assessment run complete: %d assessments %s",
                computed, "computed (dry-run, not persisted)" if dry_run else "persisted",
            )
    finally:
        if connector is not None:
            await connector.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute governance assessments from proxy data")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of proxy filings")
    parser.add_argument(
        "--no-mine-red-flags", action="store_true",
        help="Skip fetching/mining DEF 14A body text for structural red flags (faster, no network I/O)",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, mine_red_flags=not args.no_mine_red_flags))


if __name__ == "__main__":
    main()
