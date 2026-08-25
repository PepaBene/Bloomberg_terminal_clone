"""Verify a claim is actually supported by its cited source chunk(s).

A lightweight lexical-overlap heuristic, not a second LLM call (that would be
circular and doubly expensive within the same agent turn). Meant for the
agent to self-check a claim before finalizing an answer via the
``citation_check`` tool; ``src/ai/guardrails/citations.py`` (next Phase 0
item) reuses ``check_claim_support`` as a post-hoc enforcement gate on the
finished response, so a claim that talks its way past the agent still gets
caught once.

``check_claim_support`` is pure (no DB) and fully unit-testable;
``CitationCheckTool.run`` is the thin async wrapper that resolves
``document_ids`` to their stored chunk text.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.tools.base import BaseTool, ToolResult

SUPPORT_THRESHOLD = 0.6

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.%$]*")

# Common words carry no evidentiary weight for "is this claim supported" --
# excluding them means the overlap score reflects substantive terms (figures,
# entity names, dates, technical terms), not sentence glue.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "and", "or", "but", "with", "by",
    "as", "that", "this", "it", "its", "from", "has", "have", "had", "will",
    "would", "could", "should", "than", "then", "which", "who", "their",
}


def _significant_tokens(text: str) -> set[str]:
    return {
        t for t in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
        if len(t) >= 3 and t not in _STOPWORDS
    }


def check_claim_support(claim: str, source_text: str) -> float:
    """Fraction of the claim's significant tokens that appear in ``source_text``.

    Returns 0.0 for an empty claim or empty source. This is a coarse,
    honest heuristic (token overlap, not entailment) -- it catches claims
    that reference facts/figures absent from the cited text, not subtler
    misrepresentations of text that IS present.
    """
    claim_tokens = _significant_tokens(claim)
    if not claim_tokens:
        return 0.0
    source_tokens = _significant_tokens(source_text)
    if not source_tokens:
        return 0.0
    return len(claim_tokens & source_tokens) / len(claim_tokens)


class CitationCheckTool(BaseTool):
    """Check whether a claim is supported by its cited document chunk(s)."""

    name = "citation_check"
    description = (
        "Check whether a claim's key facts/figures actually appear in the text "
        "of the document chunk(s) it cites, before including the claim in a final answer."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "claim": {"type": "string", "description": "The claim text to verify"},
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "search_documents.id values the claim cites",
            },
        },
        "required": ["claim", "document_ids"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, claim: str, document_ids: list[str]) -> ToolResult:
        from src.models.semantic_search import SearchDocument

        ids: list[uuid.UUID] = []
        for d in document_ids or []:
            try:
                ids.append(uuid.UUID(d))
            except (ValueError, AttributeError, TypeError):
                continue
        if not ids:
            return ToolResult(content="No valid document_ids provided — claim is NOT grounded.")

        rows = (
            await self._session.execute(
                select(SearchDocument.chunk_text).where(SearchDocument.id.in_(ids))
            )
        ).scalars().all()
        if not rows:
            return ToolResult(content="Cited document_ids not found — claim is NOT grounded.")

        score = check_claim_support(claim, " ".join(rows))
        supported = score >= SUPPORT_THRESHOLD
        return ToolResult(
            content=f"supported={supported} overlap_score={score:.2f} "
            f"(threshold={SUPPORT_THRESHOLD})"
        )
