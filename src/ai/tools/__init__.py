"""Claude tool-use tools, shared by all agents (src/ai/agents/).

Public surface:
    from src.ai.tools import BaseTool, ToolResult
    from src.ai.tools import DataQueryTool, CitationCheckTool
    from src.ai.tools import web_search_tool_spec
"""
from src.ai.tools.base import BaseTool, ToolResult
from src.ai.tools.citation_check import CitationCheckTool, check_claim_support
from src.ai.tools.data_query import DataQueryTool
from src.ai.tools.web_search import DEFAULT_ALLOWED_DOMAINS, web_search_tool_spec

__all__ = [
    "BaseTool",
    "ToolResult",
    "DataQueryTool",
    "CitationCheckTool",
    "check_claim_support",
    "web_search_tool_spec",
    "DEFAULT_ALLOWED_DOMAINS",
]
