"""Generic Claude tool-use agent loop.

``AIClient.complete(tools=..., tool_choice=...)`` is single-shot: it returns
whatever ``tool_use`` blocks the model emits but doesn't execute them or feed
results back. This is the multi-turn extension -- call the model, if it asks
to use a client tool execute it via the registry and append a ``tool_result``,
call again, repeat until the model emits a final text-only answer or the
iteration cap is hit. Every one of Layer 1/2/3's agents (``interpreter.py``,
``researcher.py``, ``adviser.py``) is this loop with a different system
prompt + tool set.

Accepts anything duck-typed like ``AIClient`` (``enabled`` + async
``complete(...)``), not the concrete class -- this is what makes the loop
testable with a hand-rolled fake client returning canned ``AIResponse``
sequences, without needing the real ``anthropic`` package or a live key.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.ai.models import DEFAULT_TIER, Tier
from src.ai.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 8


class AIClientLike(Protocol):
    """The slice of ``AIClient`` the loop actually needs — enables fakes in tests."""

    @property
    def enabled(self) -> bool: ...

    async def complete(self, **kwargs: Any) -> Any: ...


@dataclass
class AgentStep:
    """One turn of the loop, kept for tracing/telemetry/debugging."""

    role: str  # "assistant"
    text: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    final_text: str
    steps: list[AgentStep]
    iterations: int
    stopped_reason: str  # "final_answer" | "max_iterations"


async def run_agent(
    *,
    client: AIClientLike,
    system: str,
    user: str,
    tools: list[BaseTool] | None = None,
    server_tools: list[dict[str, Any]] | None = None,
    tier: Tier | str = DEFAULT_TIER,
    model: str | None = None,
    max_tokens: int = 2048,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    feature: str = "agent",
    user_id: str | None = None,
    on_step: Callable[[AgentStep], Awaitable[None]] | None = None,
) -> AgentResult:
    """Run the tool-use loop until Claude emits a final text-only answer.

    ``tools`` are executed locally (``BaseTool.run``); ``server_tools`` are
    raw Anthropic server-tool specs (e.g. ``web_search``) that Claude
    resolves itself -- see ``tools/base.py``'s module docstring for why
    these never reach local dispatch.

    ``on_step``, when given, is awaited with each ``AgentStep`` right after
    it's appended (including the final text-only one) -- the hook a caller
    needs to stream per-step progress (e.g. over SSE) without this loop
    knowing anything about HTTP/SSE itself.
    """
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")

    tools = tools or []
    server_tools = server_tools or []
    tool_specs = [t.spec() for t in tools] + list(server_tools)
    tool_by_name = {t.name: t for t in tools}

    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
    steps: list[AgentStep] = []

    for i in range(max_iterations):
        resp = await client.complete(
            messages=messages,
            system=system,
            tier=tier,
            model=model,
            max_tokens=max_tokens,
            tools=tool_specs or None,
            feature=feature,
            user_id=user_id,
        )

        if not resp.tool_uses:
            final_step = AgentStep(role="assistant", text=resp.text)
            steps.append(final_step)
            if on_step is not None:
                await on_step(final_step)
            return AgentResult(
                final_text=resp.text, steps=steps, iterations=i + 1,
                stopped_reason="final_answer",
            )

        # Re-append the assistant turn's raw content blocks verbatim (text +
        # tool_use blocks, in Anthropic's own shape) so tool_use ids line up
        # with the tool_result blocks the next message carries.
        messages.append({"role": "assistant", "content": resp.raw.content})

        tool_calls: list[dict[str, Any]] = []
        tool_result_blocks: list[dict[str, Any]] = []
        for block in resp.tool_uses:
            name = getattr(block, "name", None)
            tool_input = getattr(block, "input", None) or {}
            tool_use_id = getattr(block, "id", None)
            tool_calls.append({"name": name, "input": tool_input, "tool_use_id": tool_use_id})

            tool = tool_by_name.get(name)
            if tool is None:
                result = ToolResult(content=f"Unknown tool: {name}", is_error=True)
            else:
                try:
                    result = await tool.run(**tool_input)
                except Exception as e:  # noqa: BLE001
                    logger.warning("tool %r failed: %s", name, e)
                    result = ToolResult(content=f"Tool error: {e}", is_error=True)

            tool_result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result.content,
                "is_error": result.is_error,
            })

        step = AgentStep(
            role="assistant",
            text=resp.text or None,
            tool_calls=tool_calls,
            tool_results=[
                {"tool_use_id": b["tool_use_id"], "content": b["content"], "is_error": b["is_error"]}
                for b in tool_result_blocks
            ],
        )
        steps.append(step)
        if on_step is not None:
            await on_step(step)
        messages.append({"role": "user", "content": tool_result_blocks})

    logger.warning("agent loop hit max_iterations=%d without a final answer (feature=%s)", max_iterations, feature)
    return AgentResult(final_text="", steps=steps, iterations=max_iterations, stopped_reason="max_iterations")
