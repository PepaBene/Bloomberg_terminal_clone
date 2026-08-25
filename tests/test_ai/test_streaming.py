"""Unit tests for src/ai/streaming.py."""
from __future__ import annotations

import json

import pytest

from src.ai.streaming import (
    SSEEvent,
    format_sse,
    sse_response,
    stream_sections_as_sse,
    stream_tokens_as_sse,
)


# --------------------------------------------------------------------------- #
# format_sse (pure)
# --------------------------------------------------------------------------- #
def test_format_sse_string_data():
    out = format_sse(SSEEvent(event="token", data="hello"))
    assert out == "event: token\ndata: hello\n\n"


def test_format_sse_json_data():
    out = format_sse(SSEEvent(event="done", data={"ok": True}))
    assert out.startswith("event: done\n")
    assert 'data: {"ok": true}' in out
    assert out.endswith("\n\n")


def test_format_sse_multiline_data_uses_repeated_data_lines():
    out = format_sse(SSEEvent(event="token", data="line one\nline two"))
    lines = out.split("\n")
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert data_lines == ["data: line one", "data: line two"]


def test_format_sse_empty_string_data():
    out = format_sse(SSEEvent(event="token", data=""))
    assert out == "event: token\ndata: \n\n"


# --------------------------------------------------------------------------- #
# stream_tokens_as_sse
# --------------------------------------------------------------------------- #
async def _gen(items):
    for x in items:
        yield x


async def test_stream_tokens_as_sse_happy_path():
    events = [e async for e in stream_tokens_as_sse(_gen(["Hello", " ", "world"]))]
    assert events[0] == format_sse(SSEEvent(event="token", data="Hello"))
    assert events[-1] == format_sse(SSEEvent(event="done", data={}))
    assert len(events) == 4  # 3 tokens + done


async def test_stream_tokens_as_sse_skips_empty_chunks():
    events = [e async for e in stream_tokens_as_sse(_gen(["a", "", "b"]))]
    token_events = [e for e in events if "event: token" in e]
    assert len(token_events) == 2


async def test_stream_tokens_as_sse_emits_error_event_on_failure():
    async def failing_gen():
        yield "partial"
        raise RuntimeError("upstream broke")

    events = [e async for e in stream_tokens_as_sse(failing_gen())]
    assert "event: token" in events[0]
    assert "event: error" in events[-1]
    payload = json.loads(events[-1].split("data: ", 1)[1].strip())
    assert "upstream broke" in payload["message"]


# --------------------------------------------------------------------------- #
# stream_sections_as_sse
# --------------------------------------------------------------------------- #
async def test_stream_sections_as_sse_brackets_each_section():
    async def sections():
        yield ("headlines", _gen(["Top ", "story"]))
        yield ("watchlist", _gen(["AAPL up"]))

    events = [e async for e in stream_sections_as_sse(sections())]
    kinds = [e.split("\n")[0] for e in events]
    assert kinds == [
        "event: section_start", "event: token", "event: token", "event: section_end",
        "event: section_start", "event: token", "event: section_end",
        "event: done",
    ]


async def test_stream_sections_as_sse_error_mid_section():
    async def bad_tokens():
        yield "ok"
        raise ValueError("boom")

    async def sections():
        yield ("section1", bad_tokens())

    events = [e async for e in stream_sections_as_sse(sections())]
    assert "event: error" in events[-1]
    assert "boom" in events[-1]


# --------------------------------------------------------------------------- #
# sse_response
# --------------------------------------------------------------------------- #
def test_sse_response_returns_streaming_response_with_correct_media_type():
    from fastapi.responses import StreamingResponse

    resp = sse_response(_gen(["a"]))
    assert isinstance(resp, StreamingResponse)
    assert resp.media_type == "text/event-stream"
    assert resp.headers["Cache-Control"] == "no-cache"
