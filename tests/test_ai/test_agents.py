"""Unit tests for the tool-use agent loop (src/ai/agents/loop.py).

The `anthropic` package isn't installed in this test env, so these exercise
the loop's actual control flow (tool dispatch, message threading, stopping
conditions) against a hand-rolled fake client returning canned AIResponse
sequences -- not against the disabled-client path alone, which would leave
the interesting logic completely uncovered.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.agents.loop import run_agent
from src.ai.client import AIResponse
from src.ai.tools.base import BaseTool, ToolResult


def _tool_use_response(*, text: str, tool_name: str, tool_input: dict, tool_id: str = "tu_1") -> AIResponse:
    block = SimpleNamespace(type="tool_use", name=tool_name, input=tool_input, id=tool_id)
    return AIResponse(
        text=text,
        tool_uses=[block],
        stop_reason="tool_use",
        raw=SimpleNamespace(content=[block]),
    )


def _final_response(text: str) -> AIResponse:
    block = SimpleNamespace(type="text", text=text)
    return AIResponse(text=text, tool_uses=[], stop_reason="end_turn", raw=SimpleNamespace(content=[block]))


class FakeAIClient:
    """Duck-typed stand-in for AIClient — returns queued responses in order."""

    def __init__(self, responses: list[AIResponse], *, enabled: bool = True):
        self._responses = list(responses)
        self._enabled = enabled
        self.calls: list[dict] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeAIClient ran out of queued responses")
        return self._responses.pop(0)


class EchoTool(BaseTool):
    name = "echo"
    description = "Echoes its input back."
    input_schema = {"type": "object", "properties": {"value": {"type": "string"}}}

    def __init__(self):
        self.calls: list[dict] = []

    async def run(self, **kwargs) -> ToolResult:
        self.calls.append(kwargs)
        return ToolResult(content=f"echo:{kwargs.get('value')}")


class FailingTool(BaseTool):
    name = "boom"
    description = "Always raises."
    input_schema = {"type": "object", "properties": {}}

    async def run(self, **kwargs) -> ToolResult:
        raise RuntimeError("kaboom")


async def test_run_agent_final_answer_no_tools_needed():
    client = FakeAIClient([_final_response("just an answer, no tools needed")])
    result = await run_agent(client=client, system="sys", user="hi")
    assert result.stopped_reason == "final_answer"
    assert result.final_text == "just an answer, no tools needed"
    assert result.iterations == 1
    assert len(client.calls) == 1


async def test_run_agent_executes_tool_then_finalizes():
    tool = EchoTool()
    client = FakeAIClient([
        _tool_use_response(text="", tool_name="echo", tool_input={"value": "ping"}),
        _final_response("done, used the echo tool"),
    ])
    result = await run_agent(client=client, system="sys", user="hi", tools=[tool])

    assert result.stopped_reason == "final_answer"
    assert result.final_text == "done, used the echo tool"
    assert result.iterations == 2
    assert tool.calls == [{"value": "ping"}]

    # first step recorded the tool call + its result
    assert result.steps[0].tool_calls[0]["name"] == "echo"
    assert result.steps[0].tool_results[0]["content"] == "echo:ping"

    # second API call's message history carries the tool_result back
    second_call_messages = client.calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert second_call_messages[-1]["content"][0]["content"] == "echo:ping"


async def test_run_agent_unknown_tool_name_reports_error_and_continues():
    client = FakeAIClient([
        _tool_use_response(text="", tool_name="does_not_exist", tool_input={}),
        _final_response("recovered anyway"),
    ])
    result = await run_agent(client=client, system="sys", user="hi", tools=[])
    assert result.stopped_reason == "final_answer"
    assert result.steps[0].tool_results[0]["is_error"] is True
    assert "Unknown tool" in result.steps[0].tool_results[0]["content"]


async def test_run_agent_tool_exception_becomes_error_result_not_a_crash():
    client = FakeAIClient([
        _tool_use_response(text="", tool_name="boom", tool_input={}),
        _final_response("recovered from tool failure"),
    ])
    result = await run_agent(client=client, system="sys", user="hi", tools=[FailingTool()])
    assert result.stopped_reason == "final_answer"
    assert result.steps[0].tool_results[0]["is_error"] is True
    assert "kaboom" in result.steps[0].tool_results[0]["content"]


async def test_run_agent_hits_max_iterations_without_final_answer():
    tool = EchoTool()
    # Every response keeps asking for another tool call — never converges.
    responses = [
        _tool_use_response(text="", tool_name="echo", tool_input={"value": str(i)})
        for i in range(5)
    ]
    client = FakeAIClient(responses)
    result = await run_agent(
        client=client, system="sys", user="hi", tools=[tool], max_iterations=3,
    )
    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 3
    assert result.final_text == ""
    assert len(client.calls) == 3


async def test_run_agent_raises_when_client_disabled():
    client = FakeAIClient([], enabled=False)
    with pytest.raises(RuntimeError):
        await run_agent(client=client, system="sys", user="hi")


async def test_run_agent_passes_server_tool_specs_through_untouched():
    client = FakeAIClient([_final_response("ok")])
    spec = {"type": "web_search_20250305", "name": "web_search"}
    await run_agent(client=client, system="sys", user="hi", server_tools=[spec])
    assert spec in client.calls[0]["tools"]
