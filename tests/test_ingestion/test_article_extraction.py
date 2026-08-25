"""Tests for Layer 2 body_text extraction (trafilatura wrapper)."""

import httpx
import pytest

from src.ingestion.article_extraction import (
    MIN_EXTRACTED_LENGTH,
    extract_body_text,
    fetch_and_extract_body_text,
)

_ARTICLE_HTML = """
<html><head><title>Acme Reports Earnings</title></head>
<body>
<nav>Home | Markets | World</nav>
<article>
<h1>Acme Corp Reports Record Quarterly Earnings</h1>
<p>The company announced quarterly results today, beating analyst
expectations by a wide margin across every reported segment.</p>
<p>Revenue grew fifteen percent year over year, driven by strong cloud
demand and continued momentum in the enterprise software business,
executives said on the earnings call.</p>
<p>Management raised full-year guidance, citing robust demand trends and
disciplined cost management across the organization.</p>
</article>
<aside class="sidebar">Subscribe now! Related articles. Advertisement.</aside>
<footer>Copyright 2026</footer>
</body></html>
"""


class TestExtractBodyText:

    def test_extracts_main_content(self):
        text = extract_body_text(_ARTICLE_HTML, url="https://example.com/a")
        assert text is not None
        assert "Record Quarterly Earnings" in text
        assert "Revenue grew fifteen percent" in text

    def test_excludes_boilerplate(self):
        text = extract_body_text(_ARTICLE_HTML, url="https://example.com/a")
        assert "Subscribe now" not in text
        assert "Advertisement" not in text

    def test_empty_html_returns_none(self):
        assert extract_body_text("", url="https://example.com/a") is None
        assert extract_body_text("   ", url="https://example.com/a") is None

    def test_too_short_extraction_returns_none(self):
        html = "<html><body><article><p>Too short.</p></article></body></html>"
        assert extract_body_text(html) is None

    def test_malformed_html_does_not_raise(self):
        # Missing closing tags, stray angle brackets -- trafilatura is
        # generally tolerant, but this must never propagate an exception.
        html = "<html><body><article><p>Unclosed paragraph <div>" + ("word " * 50)
        result = extract_body_text(html)
        assert result is None or isinstance(result, str)

    def test_minimum_length_constant_is_positive(self):
        assert MIN_EXTRACTED_LENGTH > 0


class _MockResponse:
    def __init__(self, *, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class _MockAsyncClient:
    def __init__(self, response: _MockResponse | None = None, raises: Exception | None = None):
        self._response = response
        self._raises = raises

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        if self._raises is not None:
            raise self._raises
        return self._response


class TestFetchAndExtractBodyText:

    @pytest.mark.asyncio
    async def test_successful_fetch_extracts_body(self, monkeypatch):
        mock_client = _MockAsyncClient(response=_MockResponse(text=_ARTICLE_HTML))
        monkeypatch.setattr(httpx, "AsyncClient", mock_client)

        result = await fetch_and_extract_body_text("https://example.com/a")
        assert result is not None
        assert "Record Quarterly Earnings" in result

    @pytest.mark.asyncio
    async def test_http_error_status_returns_none(self, monkeypatch):
        mock_client = _MockAsyncClient(response=_MockResponse(text="", status_code=404))
        monkeypatch.setattr(httpx, "AsyncClient", mock_client)

        result = await fetch_and_extract_body_text("https://example.com/missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, monkeypatch):
        mock_client = _MockAsyncClient(raises=httpx.ConnectError("boom"))
        monkeypatch.setattr(httpx, "AsyncClient", mock_client)

        result = await fetch_and_extract_body_text("https://unreachable.example.com/a")
        assert result is None

    @pytest.mark.asyncio
    async def test_paywalled_stub_page_returns_none(self, monkeypatch):
        stub_html = "<html><body><article><p>Subscribe to continue reading.</p></article></body></html>"
        mock_client = _MockAsyncClient(response=_MockResponse(text=stub_html))
        monkeypatch.setattr(httpx, "AsyncClient", mock_client)

        result = await fetch_and_extract_body_text("https://example.com/paywalled")
        assert result is None
