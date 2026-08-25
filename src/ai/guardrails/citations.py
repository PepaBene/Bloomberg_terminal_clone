"""Citation enforcement guardrail.

Two pure checks (no DB, no LLM call) that a caller applies to a finished
response before returning it to the user:

1. ``find_uncited_numeric_claims`` — does every sentence containing a number
   carry a bracketed citation marker at all? Cheap, catches the common case
   (a figure stated with zero citation).
2. ``verify_citations`` — for sentences that DO cite something, is the claim
   actually supported by the text behind that citation? Reuses
   ``tools/citation_check.py``'s ``check_claim_support`` heuristic.

Deliberately agnostic to the citation marker format (``[1]``, ``[doc_id]``,
whatever a given prompt/renderer uses) — callers supply a
``citation_map: {marker: source_text}`` built from whatever chunks they
already retrieved, rather than this module assuming ``search_documents.id``
UUIDs appear verbatim in the model's prose (a real citation renderer would
almost certainly use short numbered markers instead). This also keeps
``verify_citations`` pure: no second DB round-trip to resolve markers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ai.tools.citation_check import check_claim_support

SUPPORT_THRESHOLD = 0.6

_SENTENCE_RE = re.compile(r"\S.*?(?:(?<=[.!?])\s+|\Z)", re.DOTALL)
_NUMBER_RE = re.compile(r"\d")
_CITATION_RE = re.compile(r"\[([^\[\]]+)\]")


def _split_sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


@dataclass(frozen=True)
class CitationIssue:
    sentence: str
    reason: str  # "missing_citation" | "unsupported_citation"
    markers: list[str] = field(default_factory=list)
    score: float | None = None


def find_uncited_numeric_claims(text: str) -> list[CitationIssue]:
    """Sentences containing a digit with no ``[marker]`` citation at all."""
    return [
        CitationIssue(sentence=sent, reason="missing_citation")
        for sent in _split_sentences(text)
        if _NUMBER_RE.search(sent) and not _CITATION_RE.search(sent)
    ]


def extract_cited_sentences(text: str) -> list[tuple[str, list[str]]]:
    """``(sentence, [citation markers])`` for every sentence that cites something."""
    out = []
    for sent in _split_sentences(text):
        markers = _CITATION_RE.findall(sent)
        if markers:
            out.append((sent, markers))
    return out


def verify_citations(
    text: str,
    citation_map: dict[str, str],
    *,
    threshold: float = SUPPORT_THRESHOLD,
) -> list[CitationIssue]:
    """Flag cited sentences whose claim isn't supported by any of their markers' text.

    A sentence citing multiple markers passes if ANY one of them supports it
    (a claim can legitimately combine/summarize several sources); it's only
    flagged when every cited marker's source text fails the overlap check,
    or when a marker isn't in ``citation_map`` at all (fabricated/unresolved
    citation).
    """
    issues = []
    for sent, markers in extract_cited_sentences(text):
        best_score = 0.0
        for marker in markers:
            source = citation_map.get(marker)
            if source is None:
                continue
            best_score = max(best_score, check_claim_support(sent, source))
        if best_score < threshold:
            issues.append(CitationIssue(
                sentence=sent, reason="unsupported_citation",
                markers=markers, score=best_score,
            ))
    return issues


def check_response(
    text: str,
    citation_map: dict[str, str],
    *,
    threshold: float = SUPPORT_THRESHOLD,
) -> list[CitationIssue]:
    """Run both checks and return the combined issue list."""
    return find_uncited_numeric_claims(text) + verify_citations(
        text, citation_map, threshold=threshold
    )
