"""Fetch a specific URL's full page text (Layer 2 §4.6's "web_fetch" half
of "web_search + web_fetch + internal data tools" -- web_search is the
Anthropic server tool in ``web_search.py``; this is the client-tool
complement for reading one page a search result pointed at).

Reuses ``src.ingestion.article_extraction``'s trafilatura-based
extraction (built for Phase 2.3's news body_text backfill) rather than
duplicating HTTP-fetch + main-content-extraction logic -- "read a URL's
article text" is the same operation whether the caller is an ingestion
connector or a research agent.
"""
from __future__ import annotations

from src.ai.tools.base import BaseTool, ToolResult
from src.ingestion.article_extraction import fetch_and_extract_body_text

# Same rationale as analyzer.py's MAX_BODY_CHARS -- an agent's tool-result
# budget shouldn't be spent on a single multi-thousand-word page when a
# few paragraphs of grounding is what's actually needed.
MAX_FETCH_CHARS = 6000


class WebFetchTool(BaseTool):
    """Fetch one URL and return its extracted article text."""

    name = "web_fetch"
    description = (
        "Fetch a specific web page by URL and return its main article text "
        "(ads/nav/boilerplate stripped). Use this to read a page a web_search "
        "result pointed at, not to discover new URLs -- use web_search for that."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
        },
        "required": ["url"],
    }

    async def run(self, *, url: str) -> ToolResult:
        if not url or not url.startswith(("http://", "https://")):
            return ToolResult(content=f"Invalid URL: {url!r}", is_error=True)

        text = await fetch_and_extract_body_text(url)
        if text is None:
            return ToolResult(
                content=f"Could not fetch or extract article text from {url} "
                "(unreachable, paywalled, or no confident main-content block).",
                is_error=True,
            )
        if len(text) > MAX_FETCH_CHARS:
            text = text[:MAX_FETCH_CHARS].rsplit(" ", 1)[0] + "…"
        return ToolResult(content=text)
