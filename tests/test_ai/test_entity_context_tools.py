"""Tests for src/ai/tools/entity_context.py (Layer 3 §5.2 context tools:
adviser read access to Layer 1 interpretations and Layer 2 news/research
reports)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.ai.tools.entity_context import (
    InterpretationLookupTool,
    RecentNewsTool,
    ResearchReportLookupTool,
)
from src.models.entity import Entity
from src.models.interpretation import Interpretation
from src.models.news_article import ArticleEntityLink, NewsArticle
from src.models.research_report import ResearchReport


async def _seed_entity(session, **kwargs) -> Entity:
    defaults = dict(
        entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY", legal_name="Acme Corp",
        status="ACTIVE", source="TEST",
    )
    defaults.update(kwargs)
    e = Entity(**defaults)
    session.add(e)
    await session.flush()
    return e


@pytest.mark.asyncio
class TestInterpretationLookupTool:

    async def test_invalid_entity_id(self, session):
        tool = InterpretationLookupTool(session)
        result = await tool.run(entity_id="not-a-uuid")
        assert result.is_error is True

    async def test_no_interpretation_found(self, session):
        e = await _seed_entity(session)
        tool = InterpretationLookupTool(session)
        result = await tool.run(entity_id=str(e.entity_id))
        assert "No Layer 1 interpretation" in result.content

    async def test_returns_subject_interpretation(self, session):
        e = await _seed_entity(session)
        session.add(Interpretation(
            id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(e.entity_id),
            scope="SUBJECT", as_of=date(2026, 1, 1),
            interpretation="Margin compression is flowing through to a lower DCF value.",
            trend="DETERIORATING", direction="UNFAVORABLE",
            drivers=["operating_margin_decline"], consequences=["lower_dcf_value"],
        ))
        await session.flush()
        tool = InterpretationLookupTool(session)

        result = await tool.run(entity_id=str(e.entity_id))
        assert "Margin compression" in result.content
        assert "DETERIORATING" in result.content
        assert "operating_margin_decline" in result.content

    async def test_returns_metric_scoped_interpretation(self, session):
        e = await _seed_entity(session)
        session.add(Interpretation(
            id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(e.entity_id),
            scope="METRIC", metric_key="ROE", as_of=date(2026, 1, 1),
            interpretation="ROE of 18% is favorable.",
        ))
        await session.flush()
        tool = InterpretationLookupTool(session)

        result = await tool.run(entity_id=str(e.entity_id), metric_key="roe")
        assert "ROE of 18%" in result.content


@pytest.mark.asyncio
class TestRecentNewsTool:

    async def test_invalid_entity_id(self, session):
        tool = RecentNewsTool(session)
        result = await tool.run(entity_id="not-a-uuid")
        assert result.is_error is True

    async def test_no_news_found(self, session):
        e = await _seed_entity(session)
        tool = RecentNewsTool(session)
        result = await tool.run(entity_id=str(e.entity_id))
        assert "No news articles" in result.content

    async def test_returns_recent_articles(self, session):
        e = await _seed_entity(session)
        article = NewsArticle(
            id=uuid.uuid4(), source_url="https://reuters.com/acme-news", title="Acme reports earnings",
            summary="Summary.", source_name="Reuters", publish_date=date(2026, 1, 10),
            ingest_date=date(2026, 1, 10), credibility_score=Decimal("0.9000"),
            sentiment_label="POSITIVE",
            ai_analysis={"interpretation": "This is a strong signal for margin recovery."},
        )
        session.add(article)
        await session.flush()
        session.add(ArticleEntityLink(id=uuid.uuid4(), article_id=article.id, entity_id=e.entity_id, is_primary=True))
        await session.flush()
        tool = RecentNewsTool(session)

        result = await tool.run(entity_id=str(e.entity_id))
        assert "Acme reports earnings" in result.content
        assert "0.90" in result.content
        assert "margin recovery" in result.content


@pytest.mark.asyncio
class TestResearchReportLookupTool:

    async def test_invalid_entity_id(self, session):
        tool = ResearchReportLookupTool(session)
        result = await tool.run(entity_id="not-a-uuid")
        assert result.is_error is True

    async def test_no_report_found(self, session):
        e = await _seed_entity(session)
        tool = ResearchReportLookupTool(session)
        result = await tool.run(entity_id=str(e.entity_id))
        assert "No completed Deep Research report" in result.content

    async def test_ignores_incomplete_reports(self, session):
        e = await _seed_entity(session)
        session.add(ResearchReport(
            id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(e.entity_id),
            subject_label="Acme Corp", status="PENDING",
        ))
        await session.flush()
        tool = ResearchReportLookupTool(session)

        result = await tool.run(entity_id=str(e.entity_id))
        assert "No completed Deep Research report" in result.content

    async def test_returns_completed_report_sections(self, session):
        e = await _seed_entity(session)
        session.add(ResearchReport(
            id=uuid.uuid4(), subject_type="ENTITY", subject_id=str(e.entity_id),
            subject_label="Acme Corp", status="COMPLETE",
            sections=[{"title": "Competitive Dynamics", "content": "Beta Corp is a growing threat.", "citations": []}],
            completed_at=datetime.now(timezone.utc),
        ))
        await session.flush()
        tool = ResearchReportLookupTool(session)

        result = await tool.run(entity_id=str(e.entity_id))
        assert "Competitive Dynamics" in result.content
        assert "Beta Corp" in result.content
