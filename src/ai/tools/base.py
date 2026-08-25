"""Tool protocol for the agent loop (src/ai/agents/loop.py).

Two distinct kinds of "tool" appear in Anthropic's tool-use API, and the
agent loop treats them differently:

* **Client tools** (``BaseTool`` subclasses here) — Claude emits a
  ``tool_use`` block, the loop executes ``tool.run(**input)`` locally, and
  feeds the result back as a ``tool_result`` block on the next turn.
* **Server tools** (e.g. Anthropic's built-in ``web_search``) — Claude
  executes them itself and returns ``server_tool_use``/``*_tool_result``
  blocks already resolved within the same response. These are passed as raw
  spec dicts (see ``tools/web_search.py``) and never go through
  ``BaseTool``/local dispatch at all — ``AIResponse.from_raw()`` only
  collects blocks of type ``"tool_use"`` into ``tool_uses``, so a server
  tool's blocks are simply never handed to the loop's dispatcher.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """What a client tool hands back to the agent loop.

    ``content`` becomes the ``tool_result`` block's content sent back to
    Claude verbatim -- keep it plain text/JSON-as-string, not a Python object.
    """

    content: str
    is_error: bool = False


class BaseTool(ABC):
    """A client-executed tool the agent loop can call mid-response."""

    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with Claude-provided arguments."""

    def spec(self) -> dict[str, Any]:
        """Anthropic tool spec dict for the ``tools=`` request param."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
