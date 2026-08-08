"""Semantic-boundary text chunking for retrieval ingestion.

Fixes two real gaps in the legacy ``src/services/ai/vector_search.py::chunk_text``
this replaces: ``overlap`` was accepted but never actually applied (chunks were
back-to-back with zero shared context), and there was no way to trace a chunk
back to its exact position in the source document (needed so a citation can
point at the passage it came from, not just "somewhere in doc X").

Same paragraph -> sentence -> hard-char-split cascade as the legacy chunker
(kept because it's a sound, simple heuristic), but chunks are packed from a
flat list of position-tracked units so overlap can carry real trailing units
from the previous chunk into the next one's prefix.

No tokenizer dependency in this repo -- token counts are a chars/4
approximation, same assumption ``vector_search.chunk_text`` already made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50

_SENTENCE_RE = re.compile(r"\S.*?(?:(?<=[.!?])\s+|\Z)", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    """One chunk of a source document, ready to embed and store."""

    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int


@dataclass(frozen=True)
class _Unit:
    """An indivisible piece of text (paragraph, sentence, or forced slice)
    with its position in the original document -- the packing granularity."""

    text: str
    start: int
    end: int


def _split_paragraphs(text: str) -> list[_Unit]:
    units: list[_Unit] = []
    cursor = 0
    for block in text.split("\n\n"):
        stripped = block.strip()
        if not stripped:
            cursor += len(block) + 2
            continue
        start = text.index(stripped, cursor)
        end = start + len(stripped)
        units.append(_Unit(stripped, start, end))
        cursor = end
    return units


def _split_sentences(unit: _Unit) -> list[_Unit]:
    out: list[_Unit] = []
    for m in _SENTENCE_RE.finditer(unit.text):
        sent = m.group(0).strip()
        if not sent:
            continue
        out.append(_Unit(sent, unit.start + m.start(), unit.start + m.end()))
    return out or [unit]


def _force_split(unit: _Unit, max_chars: int) -> list[_Unit]:
    out: list[_Unit] = []
    step = max(max_chars, 1)
    for i in range(0, len(unit.text), step):
        piece = unit.text[i:i + step]
        if piece.strip():
            out.append(_Unit(piece, unit.start + i, unit.start + i + len(piece)))
    return out


def _atomic_units(text: str, max_chars: int) -> list[_Unit]:
    """Cascade a document into units no larger than ``max_chars`` each."""
    units: list[_Unit] = []
    for para in _split_paragraphs(text):
        if len(para.text) <= max_chars:
            units.append(para)
            continue
        for sent in _split_sentences(para):
            if len(sent.text) <= max_chars:
                units.append(sent)
            else:
                units.extend(_force_split(sent, max_chars))
    return units


def chunk_text(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    chars_per_token: int = CHARS_PER_TOKEN,
) -> list[Chunk]:
    """Split ``text`` into overlapping, position-tracked chunks.

    Greedily packs atomic units (paragraph, falling back to sentence, falling
    back to a hard char slice for anything still too long) into chunks up to
    ``max_tokens``. When a chunk fills, the next one is seeded with however
    many trailing units of the previous chunk fit within ``overlap_tokens``,
    so retrieval context isn't lost at a chunk boundary.
    """
    if not text or not text.strip():
        return []

    max_chars = max(max_tokens * chars_per_token, 1)
    overlap_chars = max(overlap_tokens * chars_per_token, 0)
    units = _atomic_units(text, max_chars)
    if not units:
        return []

    chunks: list[Chunk] = []
    current: list[_Unit] = []
    current_len = 0

    def _flush() -> None:
        if not current:
            return
        joined = " ".join(u.text for u in current)
        chunks.append(Chunk(
            text=joined,
            index=len(chunks),
            start_char=current[0].start,
            end_char=current[-1].end,
            token_count=max(1, len(joined) // chars_per_token),
        ))

    for unit in units:
        added_len = len(unit.text) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            _flush()
            # Seed the next chunk with trailing units covering ~overlap_chars.
            # overlap_chars == 0 means the caller explicitly wants no
            # overlap -- honor that exactly (no forced carry). Otherwise,
            # same soft-cap rule as the packing loop below: always carry at
            # least one boundary unit even if it alone exceeds the budget
            # (dropping the boundary sentence entirely would defeat the
            # point of overlap), but never add a second one that would push
            # past it.
            carry: list[_Unit] = []
            carry_len = 0
            if overlap_chars > 0:
                for u in reversed(current):
                    extra = len(u.text) + (1 if carry else 0)
                    if carry and carry_len + extra > overlap_chars:
                        break
                    carry.insert(0, u)
                    carry_len += extra
            current = carry
            current_len = carry_len
            added_len = len(unit.text) + (1 if current else 0)

        current.append(unit)
        current_len += added_len

    _flush()
    return chunks
