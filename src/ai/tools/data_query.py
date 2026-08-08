"""Read-only, allow-listed accessor over computed analytics (Phase 0 first tool).

Deliberately narrow rather than a generic "run any SQL" tool: handing an LLM
a free-form SQL executor is a real injection/data-exfiltration risk. This
exposes exactly one safe, typed action -- fetch an entity's computed metrics
from ``analytics_results`` -- via bound-parameter ORM queries. The full plan's
``fundamentals.py``/``analytics.py`` tools add more typed actions the same
way as Layer 1 needs them; this is the pattern, not the complete surface.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.tools.base import BaseTool, ToolResult

MAX_LIMIT = 100


class DataQueryTool(BaseTool):
    """Fetch an entity's computed analytics metrics (read-only)."""

    name = "data_query"
    description = (
        "Fetch computed analytics metrics for an entity from analytics_results. "
        "Returns metric_name, value, unit, period, and as_of_date for each match, "
        "most recent first."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string", "description": "UUID of the entity"},
            "metric_name": {
                "type": "string",
                "description": "Optional: restrict to one metric (e.g. 'ROE', 'CURRENT_RATIO')",
            },
            "limit": {"type": "integer", "default": 20, "maximum": MAX_LIMIT},
        },
        "required": ["entity_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(
        self, *, entity_id: str, metric_name: str | None = None, limit: int = 20
    ) -> ToolResult:
        from src.models.analytics import AnalyticsResult

        try:
            entity_uuid = uuid.UUID(entity_id)
        except (ValueError, AttributeError):
            return ToolResult(content=f"Invalid entity_id: {entity_id!r}", is_error=True)

        query = (
            select(AnalyticsResult)
            .where(AnalyticsResult.entity_id == entity_uuid)
            .order_by(AnalyticsResult.as_of_date.desc())
            .limit(min(max(int(limit), 1), MAX_LIMIT))
        )
        if metric_name:
            query = query.where(AnalyticsResult.metric_name == metric_name.upper())

        rows = (await self._session.execute(query)).scalars().all()
        if not rows:
            return ToolResult(content="No analytics_results rows found for that entity/metric.")

        lines = [
            f"{r.metric_name}={r.value} {r.unit} ({r.period}, as_of={r.as_of_date}, "
            f"quality={r.data_quality})"
            for r in rows
        ]
        return ToolResult(content="\n".join(lines))
