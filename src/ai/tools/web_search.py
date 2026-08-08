"""Anthropic web_search server tool, domain-allowlisted to trusted wires.

This is NOT a ``BaseTool`` -- Claude executes web_search itself and returns
already-resolved ``server_tool_use``/``web_search_tool_result`` blocks within
the same response (see ``tools/base.py``'s module docstring). Pass
``web_search_tool_spec()``'s output via ``run_agent(server_tools=[...])`` or
directly as one of ``AIClient.complete(tools=[...])``'s entries.

Domain list matches AI_THREE_LAYER_REBUILD_PLAN.md §10's decided free-first
news tier (wires + regulators), not arbitrary -- extend deliberately, not by
default, since a wider allowlist changes what "trusted" means for anything
downstream that treats a web_search citation as a credible source.
"""
from __future__ import annotations

WEB_SEARCH_TOOL_TYPE = "web_search_20250305"

TRUSTED_NEWS_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "apnews.com",
    "washingtonpost.com", "cnbc.com", "marketwatch.com", "barrons.com",
    "economist.com",
]
TRUSTED_REGULATORY_DOMAINS = [
    "sec.gov", "federalreserve.gov", "ecb.europa.eu", "bankofengland.co.uk",
]
DEFAULT_ALLOWED_DOMAINS = TRUSTED_NEWS_DOMAINS + TRUSTED_REGULATORY_DOMAINS

DEFAULT_MAX_USES = 5


def web_search_tool_spec(
    *,
    max_uses: int = DEFAULT_MAX_USES,
    allowed_domains: list[str] | None = None,
) -> dict:
    """Build the Anthropic web_search tool spec for a ``tools=`` request param."""
    return {
        "type": WEB_SEARCH_TOOL_TYPE,
        "name": "web_search",
        "max_uses": max_uses,
        "allowed_domains": allowed_domains if allowed_domains is not None else DEFAULT_ALLOWED_DOMAINS,
    }
