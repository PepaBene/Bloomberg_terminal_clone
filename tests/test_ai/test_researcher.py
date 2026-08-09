"""Unit tests for src/ai/research/researcher.py."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.agents.loop import AgentStep
from src.ai.client import AIResponse
from src.ai.research.researcher import (
    ResearchReportOutput,
    gather_research,
    render_transcript,
    run_deep_research,
    structure_report,
)


def _tool_use_response(*, text: str, tool_name: str, tool_input: dict, tool_id: str = "tu_1") -> AIResponse:
    block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=tool_id)
    return AIResponse(text=text, tool_uses=[block], stop_reason="tool_use", raw=SimpleNamespace(content=[block]))


def _final_response(text: str) -> AIResponse:
    block = SimpleNamespace(type="text", text=text)
    return AIResponse(text=text, tool_uses=[], stop_reason="end_turn", raw=SimpleNamespace(content=[block]))


class FakeAgentClient:
    """Duck-typed client supporting both complete() (for run_agent, used by
    gather_research) and complete_structured() (for structure_report)."""

    def __init__(self, *, enabled: bool = True, complete_responses=None, structured_response=None):
        self.enabled = enabled
        self._complete_responses = list(complete_responses or [])
        self._structured_response = structured_response
        self.complete_calls: list[dict] = []
        self.structured_calls: list[dict] = []

    async def complete(self, **kwargs):
        self.complete_calls.append(kwargs)
        if not self._complete_responses:
            raise AssertionError("FakeAgentClient ran out of queued complete() responses")
        return self._complete_responses.pop(0)

    async def complete_structured(self, **kwargs):
        self.structured_calls.append(kwargs)
        return self._structured_response


class TestRenderTranscript:

    def test_empty_steps(self):
        assert "no research steps" in render_transcript([])

    def test_renders_text_only_step(self):
        steps = [AgentStep(role="assistant", text="Found nothing notable.")]
        result = render_transcript(steps)
        assert "analyst notes" in result
        assert "Found nothing notable." in result

    def test_renders_tool_call_and_result(self):
        steps = [AgentStep(
            role="assistant", text=None,
            tool_calls=[{"name": "web_search", "input": {"query": "Acme Corp news"}, "tool_use_id": "t1"}],
            tool_results=[{"tool_use_id": "t1", "content": "Acme reported record earnings.", "is_error": False}],
        )]
        result = render_transcript(steps)
        assert "web_search" in result
        assert "Acme Corp news" in result
        assert "Acme reported record earnings." in result
        assert "OK" in result

    def test_marks_error_results(self):
        steps = [AgentStep(
            role="assistant", text=None,
            tool_calls=[{"name": "web_fetch", "input": {"url": "https://bad.example"}, "tool_use_id": "t1"}],
            tool_results=[{"tool_use_id": "t1", "content": "fetch failed", "is_error": True}],
        )]
        result = render_transcript(steps)
        assert "ERROR" in result


@pytest.mark.asyncio
class TestGatherResearch:

    async def test_disabled_client_raises(self, session):
        client = FakeAgentClient(enabled=False)
        with pytest.raises(RuntimeError):
            await gather_research(client, session, subject_label="Acme Corp")

    async def test_runs_agent_loop_and_returns_result(self, session):
        client = FakeAgentClient(complete_responses=[
            _tool_use_response(text="", tool_name="web_search", tool_input={"query": "Acme"}),
            _final_response("Acme is doing well per several sources."),
        ])
        result = await gather_research(client, session, subject_label="Acme Corp", focus="competitive risk")

        assert result.stopped_reason == "final_answer"
        assert result.final_text == "Acme is doing well per several sources."
        # subject + focus reached the user message
        first_call_messages = client.complete_calls[0]["messages"]
        assert "Acme Corp" in first_call_messages[0]["content"]
        assert "competitive risk" in first_call_messages[0]["content"]

    async def test_on_step_hook_is_forwarded(self, session):
        client = FakeAgentClient(complete_responses=[_final_response("done")])
        seen = []

        async def on_step(step):
            seen.append(step)

        await gather_research(client, session, subject_label="Acme Corp", on_step=on_step)
        assert len(seen) == 1


@pytest.mark.asyncio
class TestStructureReport:

    async def test_returns_structured_output(self, session):
        from src.ai.agents.loop import AgentResult

        agent_result = AgentResult(
            final_text="Acme faces competitive pressure from Beta Corp.",
            steps=[AgentStep(role="assistant", text="Acme faces competitive pressure from Beta Corp.")],
            iterations=1, stopped_reason="final_answer",
        )
        expected = ResearchReportOutput(
            sections=[{"title": "Competitive Dynamics", "content": "Beta Corp is a growing threat.", "citations": ["Reuters"]}],
            sources=["Reuters"], confidence=0.7,
        )
        client = FakeAgentClient(structured_response=expected)

        result = await structure_report(client, agent_result, subject_label="Acme Corp")
        assert result == expected
        assert len(client.structured_calls) == 1
        prompt = client.structured_calls[0]["user"]
        assert "Acme Corp" in prompt
        assert "Beta Corp" in prompt


@pytest.mark.asyncio
class TestRunDeepResearch:

    async def test_full_pipeline(self, session):
        expected = ResearchReportOutput(
            sections=[{"title": "Overview", "content": "All is well.", "citations": []}],
            sources=[], confidence=0.6,
        )
        client = FakeAgentClient(
            complete_responses=[_final_response("All is well per initial research.")],
            structured_response=expected,
        )
        result = await run_deep_research(client, session, subject_label="Acme Corp")
        assert result == expected
        assert len(client.complete_calls) == 1
        assert len(client.structured_calls) == 1

    async def test_disabled_client_raises_before_structuring(self, session):
        client = FakeAgentClient(enabled=False)
        with pytest.raises(RuntimeError):
            await run_deep_research(client, session, subject_label="Acme Corp")
        assert len(client.structured_calls) == 0
