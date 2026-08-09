"""Unit tests for src/ai/tools/web_fetch.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.ai.tools.web_fetch import MAX_FETCH_CHARS, WebFetchTool


@pytest.mark.asyncio
class TestWebFetchTool:

    async def test_rejects_invalid_url(self):
        tool = WebFetchTool()
        result = await tool.run(url="not-a-url")
        assert result.is_error is True
        assert "Invalid URL" in result.content

    async def test_returns_extracted_text(self):
        tool = WebFetchTool()
        with patch(
            "src.ai.tools.web_fetch.fetch_and_extract_body_text",
            new=AsyncMock(return_value="Acme Corp reported strong earnings this quarter."),
        ):
            result = await tool.run(url="https://reuters.com/acme-earnings")
        assert result.is_error is False
        assert "Acme Corp reported strong earnings" in result.content

    async def test_extraction_miss_returns_error_result(self):
        tool = WebFetchTool()
        with patch(
            "src.ai.tools.web_fetch.fetch_and_extract_body_text",
            new=AsyncMock(return_value=None),
        ):
            result = await tool.run(url="https://paywalled.example/story")
        assert result.is_error is True
        assert "Could not fetch" in result.content

    async def test_truncates_long_text(self):
        tool = WebFetchTool()
        long_text = "word " * 3000
        with patch(
            "src.ai.tools.web_fetch.fetch_and_extract_body_text",
            new=AsyncMock(return_value=long_text),
        ):
            result = await tool.run(url="https://reuters.com/long-article")
        assert len(result.content) <= MAX_FETCH_CHARS + 1
        assert result.content.endswith("…")

    async def test_spec_shape(self):
        tool = WebFetchTool()
        spec = tool.spec()
        assert spec["name"] == "web_fetch"
        assert "url" in spec["input_schema"]["properties"]
