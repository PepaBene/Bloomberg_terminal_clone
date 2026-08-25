"""Unit tests for src/ai/news/analyzer.py."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.ai.news.analyzer import (
    ArticleAnalysisOutput,
    MAX_BODY_CHARS,
    _body_for_prompt,
    _non_consensus_note,
    _render_connections,
    analyze_article,
)
from src.models.entity import Entity
from src.models.news_article import NewsArticle, PropagationEvent


class FakeStructuredClient:
    def __init__(self, *, enabled: bool = True, response: ArticleAnalysisOutput | None = None, raises: bool = False):
        self.enabled = enabled
        self._response = response
        self._raises = raises
        self.calls: list[str] = []

    async def complete_structured(self, *, response_model, user, system, tier, max_tokens, feature):
        self.calls.append(user)
        if self._raises:
            raise RuntimeError("simulated failure")
        return self._response


def _article(**kwargs) -> NewsArticle:
    defaults = dict(
        id=uuid.uuid4(), source_url="https://reuters.com/x", title="Some headline",
        summary="Some summary.", source_name="Reuters",
        publish_date=date(2026, 1, 10), ingest_date=date(2026, 1, 10),
        corroboration_count=1, is_non_consensus=False,
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


class TestNonConsensusNote:

    def test_flagged_non_consensus(self):
        art = _article(is_non_consensus=True)
        assert "needing corroboration" in _non_consensus_note(art)

    def test_not_flagged(self):
        art = _article(is_non_consensus=False)
        assert _non_consensus_note(art) == ""


class TestBodyForPrompt:

    def test_uses_body_text_when_present(self):
        art = _article(body_text="Full body text.")
        assert _body_for_prompt(art) == "Full body text."

    def test_falls_back_to_summary(self):
        art = _article(body_text=None, summary="Just a summary.")
        assert _body_for_prompt(art) == "Just a summary."

    def test_falls_back_to_title_when_no_summary(self):
        art = _article(body_text=None, summary="", title="Only a title")
        assert _body_for_prompt(art) == "Only a title"

    def test_truncates_long_body(self):
        long_body = "word " * 2000  # well over MAX_BODY_CHARS
        art = _article(body_text=long_body)
        result = _body_for_prompt(art)
        assert len(result) <= MAX_BODY_CHARS + 1
        assert result.endswith("…")

    def test_short_body_not_truncated(self):
        art = _article(body_text="Short.")
        assert _body_for_prompt(art) == "Short."


@pytest.mark.asyncio
class TestRenderConnections:

    async def test_no_propagation_events(self, session):
        art = _article()
        session.add(art)
        await session.flush()

        result = await _render_connections(session, art)
        assert "no propagation connections" in result

    async def test_renders_propagation_events(self, session):
        art = _article()
        session.add(art)
        target = Entity(
            entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
            legal_name="Downstream Customer Corp", status="ACTIVE", source="TEST",
        )
        session.add(target)
        await session.flush()

        session.add(PropagationEvent(
            id=uuid.uuid4(), source_article_id=art.id,
            source_entity_id=uuid.uuid4(), target_entity_id=target.entity_id,
            propagation_type="CUSTOMER", hop_number=1,
            relevance_score=Decimal("0.3"), event_summary="bankruptcy at supplier",
            severity="HIGH",
        ))
        await session.flush()

        result = await _render_connections(session, art)
        assert "Downstream Customer Corp" in result
        assert "CUSTOMER" in result
        assert "HIGH" in result


@pytest.mark.asyncio
class TestAnalyzeArticle:

    async def test_disabled_client_raises(self, session):
        art = _article()
        session.add(art)
        await session.flush()
        client = FakeStructuredClient(enabled=False)

        with pytest.raises(RuntimeError):
            await analyze_article(client, session, art)

    async def test_returns_structured_output(self, session):
        art = _article()
        session.add(art)
        await session.flush()
        expected = ArticleAnalysisOutput(
            summary="A summary.", interpretation="It matters because X.",
            non_consensus_angle=None, connections=["Technology sector"], confidence=0.8,
        )
        client = FakeStructuredClient(response=expected)

        result = await analyze_article(client, session, art)
        assert result == expected
        assert len(client.calls) == 1
        assert "Some headline" in client.calls[0]

    async def test_prompt_includes_source_trust_and_corroboration(self, session):
        art = _article(source_trust=Decimal("1.00"), credibility_score=Decimal("1.0000"), corroboration_count=3)
        session.add(art)
        await session.flush()
        client = FakeStructuredClient(response=ArticleAnalysisOutput(
            summary="s", interpretation="i", confidence=0.5,
        ))

        await analyze_article(client, session, art)
        prompt = client.calls[0]
        assert "1.0" in prompt
        assert "3 independent source" in prompt
