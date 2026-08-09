"""Layer 3 (AI_THREE_LAYER_REBUILD_PLAN.md §5.2) context tools: the
adviser's read access to Layer 1's ``interpretations`` and Layer 2's
``news_articles``/``research_reports`` -- "gathers context" over the
outputs of the two layers below it, not just raw analytics
(``DataQueryTool`` already covers ``analytics_results``).

Pure reads -- unlike Layer 1/2's own compute-on-miss stores, these tools
never trigger new AI computation mid-conversation; if nothing is cached
yet, they say so and the adviser can reason without it (or the operator
can run the relevant Layer 1/2 pipeline separately).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.tools.base import BaseTool, ToolResult


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class InterpretationLookupTool(BaseTool):
    """Read Layer 1's most recent interpretation of an entity."""

    name = "interpretation_lookup"
    description = (
        "Get Layer 1's most recent grounded interpretation of an entity -- its overall "
        "narrative (trend, drivers, cross-domain connections) and, optionally, one "
        "specific metric's interpretation. Read-only: does not compute a new one."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string", "description": "UUID of the entity"},
            "metric_key": {
                "type": "string",
                "description": "Optional: a specific metric name (e.g. 'ROE') instead of the whole-subject synthesis",
            },
        },
        "required": ["entity_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, entity_id: str, metric_key: str | None = None) -> ToolResult:
        from src.models.interpretation import Interpretation

        eid = _parse_uuid(entity_id)
        if eid is None:
            return ToolResult(content=f"Invalid entity_id: {entity_id!r}", is_error=True)

        query = select(Interpretation).where(
            Interpretation.subject_type == "ENTITY", Interpretation.subject_id == str(eid),
        )
        if metric_key:
            query = query.where(Interpretation.scope == "METRIC", Interpretation.metric_key == metric_key.upper())
        else:
            query = query.where(Interpretation.scope == "SUBJECT")
        query = query.order_by(Interpretation.as_of.desc()).limit(1)

        row = (await self._session.execute(query)).scalars().first()
        if row is None:
            what = f"metric '{metric_key}'" if metric_key else "a subject-level synthesis"
            return ToolResult(content=f"No Layer 1 interpretation found for {what} on this entity yet.")

        lines = [f"As of {row.as_of}: {row.interpretation}"]
        if row.trend:
            lines.append(f"Trend: {row.trend}" + (f", direction: {row.direction}" if row.direction else ""))
        if row.drivers:
            lines.append(f"Drivers: {', '.join(str(d) for d in row.drivers)}")
        if row.consequences:
            lines.append(f"Consequences: {', '.join(str(c) for c in row.consequences)}")
        return ToolResult(content="\n".join(lines))


class RecentNewsTool(BaseTool):
    """Read Layer 2's most recent, most credible news for an entity."""

    name = "recent_news"
    description = (
        "Get an entity's most recent news coverage: title, source, credibility score, "
        "sentiment, and AI analysis (summary/interpretation) when available. Sorted by "
        "publish date, most recent first."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string", "description": "UUID of the entity"},
            "limit": {"type": "integer", "default": 5, "maximum": 20},
        },
        "required": ["entity_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, entity_id: str, limit: int = 5) -> ToolResult:
        from src.models.news_article import ArticleEntityLink, NewsArticle

        eid = _parse_uuid(entity_id)
        if eid is None:
            return ToolResult(content=f"Invalid entity_id: {entity_id!r}", is_error=True)

        rows = (
            await self._session.execute(
                select(NewsArticle)
                .join(ArticleEntityLink, ArticleEntityLink.article_id == NewsArticle.id)
                .where(ArticleEntityLink.entity_id == eid)
                .order_by(NewsArticle.publish_date.desc())
                .limit(min(max(int(limit), 1), 20))
            )
        ).scalars().all()
        if not rows:
            return ToolResult(content="No news articles found for this entity.")

        lines = []
        for a in rows:
            credibility = f"{float(a.credibility_score):.2f}" if a.credibility_score is not None else "n/a"
            line = f"[{a.publish_date}] {a.source_name}: {a.title} (credibility={credibility}, sentiment={a.sentiment_label or 'n/a'})"
            if a.ai_analysis and a.ai_analysis.get("interpretation"):
                line += f"\n  {a.ai_analysis['interpretation']}"
            lines.append(line)
        return ToolResult(content="\n".join(lines))


class ResearchReportLookupTool(BaseTool):
    """Read a completed Layer 2 Deep Research report for a subject."""

    name = "research_report_lookup"
    description = (
        "Get the most recent completed Deep Research report for an entity, if one exists "
        "-- qualitative findings (competitive dynamics, regulatory exposure, controversies, "
        "expert views) not captured by structured data. Read-only: does not start new research."
    )
    input_schema = {
        "type": "object",
        "properties": {"entity_id": {"type": "string", "description": "UUID of the entity"}},
        "required": ["entity_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, entity_id: str) -> ToolResult:
        from src.models.research_report import ResearchReport

        eid = _parse_uuid(entity_id)
        if eid is None:
            return ToolResult(content=f"Invalid entity_id: {entity_id!r}", is_error=True)

        row = (
            await self._session.execute(
                select(ResearchReport)
                .where(
                    ResearchReport.subject_type == "ENTITY", ResearchReport.subject_id == str(eid),
                    ResearchReport.status == "COMPLETE",
                )
                .order_by(ResearchReport.completed_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if row is None:
            return ToolResult(content="No completed Deep Research report found for this entity.")

        lines = [f"Research report on {row.subject_label} (completed {row.completed_at}):"]
        for section in row.sections or []:
            lines.append(f"- {section.get('title', 'Untitled')}: {section.get('content', '')}")
        return ToolResult(content="\n".join(lines))
