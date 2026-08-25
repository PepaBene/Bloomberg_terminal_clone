"""Unit tests for src/ai/news/cluster_analyzer.py."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.ai.news.cluster_analyzer import (
    ClusterSynthesisOutput,
    cluster_members,
    resolve_representative,
    synthesize_cluster,
)
from src.models.news_article import NewsArticle


class FakeStructuredClient:
    def __init__(self, *, enabled: bool = True, response: ClusterSynthesisOutput | None = None, raises: bool = False):
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
        id=uuid.uuid4(), source_url=f"https://reuters.com/{uuid.uuid4()}", title="Some headline",
        summary="Some summary.", source_name="Reuters",
        publish_date=date(2026, 1, 10), ingest_date=date(2026, 1, 10),
        corroboration_count=1, is_non_consensus=False,
    )
    defaults.update(kwargs)
    return NewsArticle(**defaults)


@pytest.mark.asyncio
class TestResolveRepresentative:

    async def test_article_is_its_own_representative(self, session):
        art = _article()
        art.cluster_id = art.id
        session.add(art)
        await session.flush()

        result = await resolve_representative(session, art)
        assert result.id == art.id

    async def test_article_with_null_cluster_id_is_its_own_representative(self, session):
        art = _article()
        session.add(art)
        await session.flush()

        result = await resolve_representative(session, art)
        assert result.id == art.id

    async def test_resolves_to_representative(self, session):
        rep = _article(title="Original story")
        rep.cluster_id = rep.id
        session.add(rep)
        await session.flush()

        follower = _article(title="Corroborating story", cluster_id=rep.id)
        session.add(follower)
        await session.flush()

        result = await resolve_representative(session, follower)
        assert result.id == rep.id


@pytest.mark.asyncio
class TestClusterMembers:

    async def test_returns_representative_and_followers(self, session):
        rep = _article(title="Original story")
        rep.cluster_id = rep.id
        session.add(rep)
        await session.flush()

        follower = _article(title="Corroborating story", cluster_id=rep.id)
        session.add(follower)
        await session.flush()

        members = await cluster_members(session, rep)
        member_ids = {m.id for m in members}
        assert member_ids == {rep.id, follower.id}

    async def test_singleton_cluster_returns_just_the_representative(self, session):
        rep = _article()
        rep.cluster_id = rep.id
        session.add(rep)
        await session.flush()

        members = await cluster_members(session, rep)
        assert [m.id for m in members] == [rep.id]


@pytest.mark.asyncio
class TestSynthesizeCluster:

    async def test_disabled_client_raises(self, session):
        rep = _article()
        rep.cluster_id = rep.id
        session.add(rep)
        await session.flush()
        client = FakeStructuredClient(enabled=False)

        with pytest.raises(RuntimeError):
            await synthesize_cluster(client, session, rep)

    async def test_returns_structured_output(self, session):
        rep = _article(title="Fed raises rates", corroboration_count=2)
        rep.cluster_id = rep.id
        session.add(rep)
        await session.flush()

        follower = _article(
            title="Fed hikes interest rates", source_name="Bloomberg", cluster_id=rep.id,
        )
        session.add(follower)
        await session.flush()

        expected = ClusterSynthesisOutput(
            consensus_summary="The Fed raised rates by 25bps.",
            divergent_views=["Bloomberg emphasizes inflation risk more heavily"],
            materiality_assessment="High materiality macro event.",
            confidence=0.85,
        )
        client = FakeStructuredClient(response=expected)

        result = await synthesize_cluster(client, session, rep)
        assert result == expected
        assert len(client.calls) == 1
        prompt = client.calls[0]
        assert "Fed raises rates" in prompt
        assert "Reuters" in prompt
        assert "Bloomberg" in prompt

    async def test_includes_existing_ai_analysis_when_present(self, session):
        rep = _article(title="Story A")
        rep.cluster_id = rep.id
        rep.ai_analysis = {"interpretation": "This matters because of X."}
        session.add(rep)
        await session.flush()

        client = FakeStructuredClient(response=ClusterSynthesisOutput(
            consensus_summary="s", materiality_assessment="m", confidence=0.5,
        ))
        await synthesize_cluster(client, session, rep)
        assert "This matters because of X." in client.calls[0]
