"""SSE streaming helper for chat/briefing/deep-research endpoints.

``AIClient.stream()`` already yields plain text deltas -- this formats them
(and, for section-streamed content like morning briefings, section
boundaries) as Server-Sent Events wire format and wraps the result in a
FastAPI ``StreamingResponse``.

No dependency on ``sse-starlette`` for the core path here (plain FastAPI
``StreamingResponse`` is sufficient for correct SSE wire format);
``sse-starlette`` (added to pyproject for this) is only worth reaching for
later if a specific endpoint wants the automatic ping/reconnect-id support
its ``EventSourceResponse`` adds on top.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

SSE_MEDIA_TYPE = "text/event-stream"


@dataclass(frozen=True)
class SSEEvent:
    """One Server-Sent Event. ``data`` is JSON-encoded unless already a str."""

    event: str  # "token" | "section_start" | "section_end" | "done" | "error"
    data: Any


def format_sse(event: SSEEvent) -> str:
    """Pure: render one ``SSEEvent`` as SSE wire format.

    Multi-line data is split across repeated ``data:`` lines per the SSE
    spec -- a single ``data: {json containing a literal newline}`` line
    would corrupt the stream for any spec-compliant client parser.
    """
    payload = event.data if isinstance(event.data, str) else json.dumps(event.data)
    lines = [f"event: {event.event}"]
    for line in (payload.splitlines() or [""]):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


async def stream_tokens_as_sse(token_iter: AsyncIterator[str]) -> AsyncIterator[str]:
    """Wrap a plain text-delta iterator (e.g. ``AIClient.stream()``'s output)
    into SSE ``token`` events, always terminated by ``done`` or ``error`` so
    the client has a definitive end signal even on mid-stream failure.
    """
    try:
        async for chunk in token_iter:
            if chunk:
                yield format_sse(SSEEvent(event="token", data=chunk))
        yield format_sse(SSEEvent(event="done", data={}))
    except Exception as e:  # noqa: BLE001
        logger.exception("stream_tokens_as_sse failed")
        yield format_sse(SSEEvent(event="error", data={"message": str(e)}))


async def stream_sections_as_sse(
    sections: AsyncIterator[tuple[str, AsyncIterator[str]]],
) -> AsyncIterator[str]:
    """For section-streamed content (morning briefings): ``sections`` yields
    ``(section_name, token_iterator)`` pairs in order; each section's tokens
    are bracketed by ``section_start``/``section_end`` events.
    """
    try:
        async for name, token_iter in sections:
            yield format_sse(SSEEvent(event="section_start", data={"name": name}))
            async for chunk in token_iter:
                if chunk:
                    yield format_sse(SSEEvent(event="token", data=chunk))
            yield format_sse(SSEEvent(event="section_end", data={"name": name}))
        yield format_sse(SSEEvent(event="done", data={}))
    except Exception as e:  # noqa: BLE001
        logger.exception("stream_sections_as_sse failed")
        yield format_sse(SSEEvent(event="error", data={"message": str(e)}))


def sse_response(generator: AsyncIterator[str]):
    """Wrap an SSE-formatted string generator in a FastAPI ``StreamingResponse``.

    Deferred import so this module (and the rest of ``src/ai/``) stays
    importable without FastAPI installed, matching the graceful-degradation
    contract the rest of the AI core follows.
    """
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        generator,
        media_type=SSE_MEDIA_TYPE,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
