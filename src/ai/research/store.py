"""Persistence for Layer 2 on-demand Deep Research runs (§4.6).

Unlike Layer 1's interpretations or this phase's article/cluster analysis
(compute-on-miss caches over an existing row), a ``ResearchReport`` IS the
job record from the start -- created PENDING before the agent runs at all,
so a caller (or an SSE stream) always has a real ``report_id`` to track
regardless of how long the multi-step agent run takes, and a failure
becomes a visible FAILED row with an error message rather than a bare
``None``.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.loop import AgentStep
from src.ai.models import model_for_tier
from src.ai.research.researcher import RESEARCH_TIER, run_deep_research
from src.models.research_report import ResearchReport

logger = logging.getLogger(__name__)


async def create_pending_report(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_label: str,
    subject_id: str | None = None,
    focus: str | None = None,
) -> ResearchReport:
    """Insert a PENDING report row and return it -- callers get a stable
    ``report_id`` before any AI work happens."""
    report = ResearchReport(
        id=uuid.uuid4(),
        subject_type=subject_type,
        subject_id=subject_id,
        subject_label=subject_label,
        focus=focus,
        status="PENDING",
    )
    session.add(report)
    await session.flush()
    return report


async def run_and_persist_research(
    session: AsyncSession,
    client,
    report: ResearchReport,
    *,
    on_step: Callable[[AgentStep], Awaitable[None]] | None = None,
) -> ResearchReport:
    """Run the deep-research pipeline for an existing report row, updating
    its status/fields in place. Never raises -- a failure (AI disabled,
    tool/model error) lands as ``status="FAILED"`` with ``error`` set,
    since this report already exists as a row a caller may be polling or
    streaming against.
    """
    report.status = "RUNNING"
    await session.flush()

    try:
        output = await run_deep_research(
            client, session, subject_label=report.subject_label,
            focus=report.focus, on_step=on_step,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("deep research failed for report %s", report.id, exc_info=True)
        report.status = "FAILED"
        report.error = f"{type(e).__name__}: {e}"[:2000]
        await session.flush()
        return report

    report.sections = [s.model_dump() for s in output.sections]
    report.sources = output.sources
    report.confidence = output.confidence
    report.model = model_for_tier(RESEARCH_TIER)
    report.status = "COMPLETE"
    report.completed_at = datetime.now(timezone.utc)
    await session.flush()
    return report
