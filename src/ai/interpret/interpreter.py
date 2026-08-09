"""Layer 1 Interpreter agent — AI_THREE_LAYER_REBUILD_PLAN.md §3.3.

Two stages:
1. **Per-metric interpretation** (LIGHT tier, structured, batched
   concurrently): for each ``MetricSnapshot``, what it means, its trend,
   direction, driver(s) drawn from its own lineage, and a confidence score.
2. **Connected synthesis** (SYNTHESIS tier): ties the per-metric reads
   together along ``src/ai/interpret/graph.py``'s curated edges into a
   causes -> consequences narrative, surfacing the graph edges that
   actually touch this subject's computed metrics (not the whole graph).

Both stages use ``complete_structured`` -- a validated Pydantic object, not
parsed free text. Neither stage persists anything; that's
``src/ai/interpret/store.py``'s job (compute-on-miss caching, the
``interpretations`` table).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.interpret import graph
from src.ai.interpret.context import MetricSnapshot, SubjectContext, assemble_entity_context
from src.ai.prompts import load_prompt

logger = logging.getLogger(__name__)


class MetricInterpretationOutput(BaseModel):
    """Structured output for the ``interpret_metric`` prompt."""

    interpretation: str
    trend: str  # IMPROVING | DETERIORATING | STABLE | UNKNOWN
    direction: str  # FAVORABLE | UNFAVORABLE | NEUTRAL
    drivers: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SubjectSynthesisOutput(BaseModel):
    """Structured output for the ``interpret_subject`` prompt."""

    interpretation: str
    trend: str
    direction: str
    drivers: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    key_connections: list[str] = Field(default_factory=list)  # 3-5 most decision-relevant, human-readable
    confidence: float = Field(ge=0.0, le=1.0)


def render_lineage(lineage: list[dict] | None) -> str:
    """Pure: render a MetricSnapshot's lineage list into readable lines for
    a prompt's ``<context>`` block. ``None``/empty -> a plain statement that
    no source detail is available (never silently omitted)."""
    if not lineage:
        return "(no source detail available for this metric)"
    lines = []
    for item in lineage:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "?")
        value = item.get("value")
        source = item.get("source")
        piece = f"- {name} = {value}"
        if source:
            piece += f" (source: {source})"
        lines.append(piece)
    return "\n".join(lines) if lines else "(no source detail available for this metric)"


async def interpret_metric(
    client, snapshot: MetricSnapshot
) -> MetricInterpretationOutput:
    """Interpret one metric snapshot. Raises if the client is disabled --
    callers batch this with ``interpret_metrics_batch``, which is
    best-effort per metric."""
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
    prompt = load_prompt("interpret_metric")
    return await client.complete_structured(
        response_model=MetricInterpretationOutput,
        user=prompt.render(
            metric_name=snapshot.metric_name,
            value=snapshot.value,
            unit=snapshot.unit,
            trend=snapshot.trend or "UNKNOWN",
            context=render_lineage(snapshot.lineage),
        ),
        system=prompt.system,
        tier=prompt.tier,
        max_tokens=prompt.max_tokens,
        feature=prompt.feature,
    )


async def interpret_metrics_batch(
    client, snapshots: list[MetricSnapshot], *, concurrency: int = 8
) -> dict[str, MetricInterpretationOutput]:
    """Interpret every snapshot concurrently (LIGHT tier, cheap/fast calls).

    Best-effort per metric: a single failure is logged and that metric is
    simply absent from the result, not a reason to fail the whole batch --
    a subject with 60 ratios shouldn't lose its interpretation entirely
    because one API call timed out.
    """
    if not client.enabled or not snapshots:
        return {}
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(s: MetricSnapshot) -> tuple[str, MetricInterpretationOutput | None]:
        async with semaphore:
            try:
                return s.metric_name, await interpret_metric(client, s)
            except Exception:  # noqa: BLE001
                logger.warning("interpret_metric failed for %s", s.metric_name, exc_info=True)
                return s.metric_name, None

    results = await asyncio.gather(*(_one(s) for s in snapshots))
    return {name: out for name, out in results if out is not None}


def _relevant_edges(ctx: SubjectContext, *, max_hops: int = 1) -> list[graph.Edge]:
    """Pure: graph edges touching any metric this subject actually has."""
    node_set = {
        node for m in ctx.metrics
        if (node := graph.metric_to_node(m.metric_name)) is not None
    }
    if not node_set:
        return []
    return graph.connected_subgraph(node_set, max_hops=max_hops)


def _render_metric_interpretations(
    metric_interps: dict[str, MetricInterpretationOutput]
) -> str:
    """Pure: render the per-metric outputs into the synthesis prompt's block."""
    if not metric_interps:
        return "(no per-metric interpretations available)"
    lines = []
    for name, out in metric_interps.items():
        lines.append(
            f"- {name}: {out.interpretation} "
            f"[trend={out.trend}, direction={out.direction}, confidence={out.confidence:.2f}]"
        )
    return "\n".join(lines)


def _render_graph_edges(edges: list[graph.Edge]) -> str:
    """Pure: render connection-graph edges into the synthesis prompt's block."""
    if not edges:
        return "(no curated cross-domain connections apply to this subject's metrics)"
    return "\n".join(f"- {e.source} -> {e.target}: {e.mechanism}" for e in edges)


async def synthesize_subject(
    client,
    ctx: SubjectContext,
    metric_interps: dict[str, MetricInterpretationOutput],
    *,
    subject_label: str,
) -> SubjectSynthesisOutput:
    """Connected synthesis across a subject's already-interpreted metrics."""
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
    edges = _relevant_edges(ctx)
    prompt = load_prompt("interpret_subject")
    return await client.complete_structured(
        response_model=SubjectSynthesisOutput,
        user=prompt.render(
            subject_label=subject_label,
            metric_interpretations=_render_metric_interpretations(metric_interps),
            graph_edges=_render_graph_edges(edges),
        ),
        system=prompt.system,
        tier=prompt.tier,
        max_tokens=prompt.max_tokens,
        feature=prompt.feature,
    )


async def interpret_entity(
    client,
    session: AsyncSession,
    entity_id: uuid.UUID,
    *,
    subject_label: str | None = None,
    as_of: date | None = None,
) -> tuple[SubjectContext, dict[str, MetricInterpretationOutput], SubjectSynthesisOutput | None]:
    """Full Layer 1 pipeline for one entity: assemble context -> per-metric
    batch -> connected synthesis. Never raises for "no data"/"AI disabled"
    cases -- returns whatever it could produce (possibly empty).
    """
    ctx = await assemble_entity_context(session, entity_id, as_of=as_of)
    if not client.enabled or not ctx.metrics:
        return ctx, {}, None

    metric_interps = await interpret_metrics_batch(client, ctx.metrics)
    if not metric_interps:
        return ctx, {}, None

    try:
        synthesis = await synthesize_subject(
            client, ctx, metric_interps, subject_label=subject_label or str(entity_id),
        )
    except Exception:  # noqa: BLE001
        logger.warning("synthesize_subject failed for entity %s", entity_id, exc_info=True)
        synthesis = None

    return ctx, metric_interps, synthesis
