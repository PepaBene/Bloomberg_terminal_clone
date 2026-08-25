"""Persistence + compute-on-miss caching for Layer 1 interpretations.

Cache key: ``(subject_type, subject_id, scope, metric_key, as_of)``. A
cached row is only reused when its ``analytics_version`` matches the
freshly-assembled ``SubjectContext``'s current ``analytics_version`` -- a
row that exists but was computed against now-stale analytics is treated as
a MISS (recomputed), not a hit, per §3.5's event-driven-refresh intent.
Per-metric: only the metrics whose analytics actually changed get
recomputed, not the whole subject -- real cost savings, not just avoided
duplicate writes.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.interpret.context import MetricSnapshot, SubjectContext, assemble_entity_context
from src.ai.interpret.interpreter import (
    MetricInterpretationOutput,
    SubjectSynthesisOutput,
    interpret_metric,
    synthesize_subject,
)
from src.ai.models import model_for_tier
from src.ai.prompts import load_prompt
from src.models.interpretation import Interpretation

logger = logging.getLogger(__name__)


async def get_interpretation(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: str,
    scope: str,
    metric_key: str | None,
    as_of: date,
) -> Interpretation | None:
    """Look up an existing row for the exact cache key. ``metric_key=None``
    correctly matches only NULL rows (SUBJECT/GROUP scope) via ``.is_(None)``
    -- a plain ``==None`` comparison would compile to always-false SQL.
    """
    query = select(Interpretation).where(
        Interpretation.subject_type == subject_type,
        Interpretation.subject_id == subject_id,
        Interpretation.scope == scope,
        Interpretation.as_of == as_of,
    )
    query = query.where(
        Interpretation.metric_key.is_(None) if metric_key is None
        else Interpretation.metric_key == metric_key
    )
    return (await session.execute(query)).scalars().first()


def _is_fresh(row: Interpretation | None, analytics_version: str) -> bool:
    return row is not None and row.analytics_version == analytics_version


async def _upsert(
    session: AsyncSession,
    *,
    existing: Interpretation | None,
    subject_type: str,
    subject_id: str,
    scope: str,
    metric_key: str | None,
    as_of: date,
    analytics_version: str,
    fields: dict,
) -> Interpretation:
    if existing is not None:
        for k, v in fields.items():
            setattr(existing, k, v)
        existing.analytics_version = analytics_version
        row = existing
    else:
        row = Interpretation(
            id=uuid.uuid4(), subject_type=subject_type, subject_id=subject_id,
            scope=scope, metric_key=metric_key, as_of=as_of,
            analytics_version=analytics_version, **fields,
        )
        session.add(row)
    await session.flush()
    return row


async def save_metric_interpretation(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: str,
    as_of: date,
    analytics_version: str,
    snapshot: MetricSnapshot,
    output: MetricInterpretationOutput,
) -> Interpretation:
    prompt = load_prompt("interpret_metric")
    existing = await get_interpretation(
        session, subject_type=subject_type, subject_id=subject_id,
        scope="METRIC", metric_key=snapshot.metric_name, as_of=as_of,
    )
    return await _upsert(
        session, existing=existing, subject_type=subject_type, subject_id=subject_id,
        scope="METRIC", metric_key=snapshot.metric_name, as_of=as_of,
        analytics_version=analytics_version,
        fields=dict(
            interpretation=output.interpretation, trend=output.trend, direction=output.direction,
            drivers=output.drivers, consequences=None, connections=None,
            confidence=output.confidence,
            citations=[f"{snapshot.source_table}:{snapshot.source_id}"],
            model=model_for_tier(prompt.tier), prompt_id=prompt.id, prompt_version=prompt.version,
            ai_enabled=True,
        ),
    )


async def save_subject_interpretation(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: str,
    as_of: date,
    analytics_version: str,
    output: SubjectSynthesisOutput,
    citations: list[str],
) -> Interpretation:
    prompt = load_prompt("interpret_subject")
    existing = await get_interpretation(
        session, subject_type=subject_type, subject_id=subject_id,
        scope="SUBJECT", metric_key=None, as_of=as_of,
    )
    return await _upsert(
        session, existing=existing, subject_type=subject_type, subject_id=subject_id,
        scope="SUBJECT", metric_key=None, as_of=as_of,
        analytics_version=analytics_version,
        fields=dict(
            interpretation=output.interpretation, trend=output.trend, direction=output.direction,
            drivers=output.drivers, consequences=output.consequences,
            connections=output.key_connections,
            confidence=output.confidence, citations=citations,
            model=model_for_tier(prompt.tier), prompt_id=prompt.id, prompt_version=prompt.version,
            ai_enabled=True,
        ),
    )


async def get_or_compute_entity_interpretation(
    session: AsyncSession,
    client,
    entity_id: uuid.UUID,
    *,
    subject_label: str | None = None,
    as_of: date | None = None,
    force_refresh: bool = False,
) -> dict:
    """Compute-on-miss entry point for one entity.

    Returns ``{"context": SubjectContext, "metrics": {metric_name: Interpretation},
    "subject": Interpretation | None}``. Metrics whose cached row is already
    fresh for the current ``analytics_version`` are reused without an LLM
    call; only stale/missing ones are (re)computed. ``force_refresh=True``
    skips the freshness check entirely (recomputes everything) -- for a
    manual "refresh" action, not the default read path.
    """
    ctx = await assemble_entity_context(session, entity_id, as_of=as_of)
    subject_id = str(entity_id)
    as_of_val = ctx.as_of
    label = subject_label or subject_id

    metric_rows: dict[str, Interpretation] = {}
    metric_outputs: dict[str, MetricInterpretationOutput] = {}

    for snapshot in ctx.metrics:
        existing = None if force_refresh else await get_interpretation(
            session, subject_type="ENTITY", subject_id=subject_id,
            scope="METRIC", metric_key=snapshot.metric_name, as_of=as_of_val,
        )
        if _is_fresh(existing, ctx.analytics_version):
            metric_rows[snapshot.metric_name] = existing
            metric_outputs[snapshot.metric_name] = MetricInterpretationOutput(
                interpretation=existing.interpretation,
                trend=existing.trend or "UNKNOWN",
                direction=existing.direction or "NEUTRAL",
                drivers=existing.drivers or [],
                confidence=float(existing.confidence) if existing.confidence is not None else 0.0,
            )
            continue
        if not client.enabled:
            continue
        try:
            output = await interpret_metric(client, snapshot)
        except Exception:  # noqa: BLE001
            logger.warning("interpret_metric failed for %s", snapshot.metric_name, exc_info=True)
            continue
        row = await save_metric_interpretation(
            session, subject_type="ENTITY", subject_id=subject_id, as_of=as_of_val,
            analytics_version=ctx.analytics_version, snapshot=snapshot, output=output,
        )
        metric_rows[snapshot.metric_name] = row
        metric_outputs[snapshot.metric_name] = output

    subject_row: Interpretation | None = None
    if metric_outputs:
        existing_subject = None if force_refresh else await get_interpretation(
            session, subject_type="ENTITY", subject_id=subject_id,
            scope="SUBJECT", metric_key=None, as_of=as_of_val,
        )
        if _is_fresh(existing_subject, ctx.analytics_version):
            subject_row = existing_subject
        elif client.enabled:
            try:
                synthesis = await synthesize_subject(
                    client, ctx, metric_outputs, subject_label=label,
                )
                citations = [f"interpretations:{r.id}" for r in metric_rows.values()]
                subject_row = await save_subject_interpretation(
                    session, subject_type="ENTITY", subject_id=subject_id, as_of=as_of_val,
                    analytics_version=ctx.analytics_version, output=synthesis, citations=citations,
                )
            except Exception:  # noqa: BLE001
                logger.warning("synthesize_subject failed for entity %s", entity_id, exc_info=True)

    return {"context": ctx, "metrics": metric_rows, "subject": subject_row}


async def get_or_compute_metric_interpretation(
    session: AsyncSession,
    client,
    entity_id: uuid.UUID,
    metric_name: str,
    *,
    as_of: date | None = None,
    force_refresh: bool = False,
) -> tuple[SubjectContext, Interpretation | None]:
    """Compute-on-miss for a SINGLE metric -- the lightweight path for a
    per-figure "Interpret this number" popover, which shouldn't have to
    wait on every other metric plus the subject synthesis to answer one
    click. Returns ``(context, None)`` if the entity has no such metric.
    """
    ctx = await assemble_entity_context(session, entity_id, as_of=as_of)
    snapshot = next((m for m in ctx.metrics if m.metric_name == metric_name), None)
    if snapshot is None:
        return ctx, None

    subject_id = str(entity_id)
    existing = None if force_refresh else await get_interpretation(
        session, subject_type="ENTITY", subject_id=subject_id,
        scope="METRIC", metric_key=metric_name, as_of=ctx.as_of,
    )
    if _is_fresh(existing, ctx.analytics_version):
        return ctx, existing
    if not client.enabled:
        # Stale or missing, and no way to compute a fresh read -- consistent
        # with get_or_compute_entity_interpretation, which simply omits a
        # metric from its result in this situation rather than silently
        # serving a row that may now contradict the current analytics.
        return ctx, None

    try:
        output = await interpret_metric(client, snapshot)
    except Exception:  # noqa: BLE001
        logger.warning("interpret_metric failed for %s", metric_name, exc_info=True)
        return ctx, None

    row = await save_metric_interpretation(
        session, subject_type="ENTITY", subject_id=subject_id, as_of=ctx.as_of,
        analytics_version=ctx.analytics_version, snapshot=snapshot, output=output,
    )
    return ctx, row
