"""Unit tests for src/ai/research/store.py."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.client import AIResponse
from src.ai.research.researcher import ResearchReportOutput
from src.ai.research.store import create_pending_report, run_and_persist_research
from src.models.research_report import ResearchReport


def _final_response(text: str) -> AIResponse:
    block = SimpleNamespace(type="text", text=text)
    return AIResponse(text=text, tool_uses=[], stop_reason="end_turn", raw=SimpleNamespace(content=[block]))


class FakeAgentClient:
    def __init__(self, *, enabled: bool = True, complete_responses=None, structured_response=None, structured_raises=False):
        self.enabled = enabled
        self._complete_responses = list(complete_responses or [])
        self._structured_response = structured_response
        self._structured_raises = structured_raises

    async def complete(self, **kwargs):
        if not self._complete_responses:
            raise AssertionError("ran out of queued complete() responses")
        return self._complete_responses.pop(0)

    async def complete_structured(self, **kwargs):
        if self._structured_raises:
            raise RuntimeError("structuring failed")
        return self._structured_response


@pytest.mark.asyncio
class TestCreatePendingReport:

    async def test_creates_row_with_pending_status(self, session):
        report = await create_pending_report(
            session, subject_type="ENTITY", subject_id="abc-123", subject_label="Acme Corp", focus="risk",
        )
        assert report.status == "PENDING"
        assert report.subject_label == "Acme Corp"
        assert report.focus == "risk"

        fetched = await session.get(ResearchReport, report.id)
        assert fetched is not None
        assert fetched.status == "PENDING"

    async def test_free_text_subject_has_no_subject_id(self, session):
        report = await create_pending_report(
            session, subject_type="FREE_TEXT", subject_label="What is the outlook for EV batteries?",
        )
        assert report.subject_id is None


@pytest.mark.asyncio
class TestRunAndPersistResearch:

    async def test_successful_run_marks_complete(self, session):
        report = await create_pending_report(
            session, subject_type="ENTITY", subject_id="e1", subject_label="Acme Corp",
        )
        expected = ResearchReportOutput(
            sections=[{"title": "Overview", "content": "Doing fine.", "citations": ["Reuters"]}],
            sources=["Reuters"], confidence=0.8,
        )
        client = FakeAgentClient(
            complete_responses=[_final_response("Doing fine per initial research.")],
            structured_response=expected,
        )

        result = await run_and_persist_research(session, client, report)

        assert result.status == "COMPLETE"
        assert result.sections == [{"title": "Overview", "content": "Doing fine.", "citations": ["Reuters"]}]
        assert result.sources == ["Reuters"]
        assert result.confidence == 0.8
        assert result.model is not None
        assert result.completed_at is not None
        assert result.error is None

    async def test_disabled_client_marks_failed(self, session):
        report = await create_pending_report(
            session, subject_type="ENTITY", subject_id="e1", subject_label="Acme Corp",
        )
        client = FakeAgentClient(enabled=False)

        result = await run_and_persist_research(session, client, report)

        assert result.status == "FAILED"
        assert result.error is not None
        assert "disabled" in result.error.lower() or "RuntimeError" in result.error

    async def test_structuring_failure_marks_failed(self, session):
        report = await create_pending_report(
            session, subject_type="ENTITY", subject_id="e1", subject_label="Acme Corp",
        )
        client = FakeAgentClient(
            complete_responses=[_final_response("some findings")],
            structured_raises=True,
        )

        result = await run_and_persist_research(session, client, report)

        assert result.status == "FAILED"
        assert "structuring failed" in result.error

    async def test_on_step_hook_is_forwarded_through_the_full_pipeline(self, session):
        report = await create_pending_report(
            session, subject_type="ENTITY", subject_id="e1", subject_label="Acme Corp",
        )
        expected = ResearchReportOutput(sections=[], sources=[], confidence=0.5)
        client = FakeAgentClient(
            complete_responses=[_final_response("done")],
            structured_response=expected,
        )
        seen = []

        async def on_step(step):
            seen.append(step)

        await run_and_persist_research(session, client, report, on_step=on_step)
        assert len(seen) == 1
