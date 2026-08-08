"""Date-consistency guardrail: reject responses with future-dated facts.

Catches the "by 2027" hallucination pattern (a stale-prompt/training-data
artifact stating something will happen at a date that's already past, or
asserting a future date as settled fact). Pure, no DB/LLM call.

Only one issue is reported per sentence (first future date found, checked
ISO -> full month-day-year -> bare-year, in that order) to avoid flagging
the same sentence two or three times for what's really one bad date.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

_SENTENCE_RE = re.compile(r"\S.*?(?:(?<=[.!?])\s+|\Z)", re.DOTALL)

_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_FULL_DATE_RE = re.compile(
    rf"\b({_MONTH_NAMES})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", re.IGNORECASE
)
# Bare year mention with no month/day (e.g. "by 2027") -- treated as an
# approximate signal only: flagging "in 2026" while today is early 2026 would
# be a false positive, so this only fires for years strictly after the
# as_of year, never the current year.
_BARE_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _split_sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


@dataclass(frozen=True)
class DateIssue:
    sentence: str
    found_date: str  # ISO date, or a bare year for the approximate case
    reason: str = "future_date"


def find_future_dated_claims(text: str, *, as_of: date | None = None) -> list[DateIssue]:
    """Sentences asserting a date strictly after ``as_of`` (default: today)."""
    as_of = as_of or date.today()
    issues: list[DateIssue] = []

    for sent in _split_sentences(text):
        m = _ISO_DATE_RE.search(sent)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                d = None
            if d and d > as_of:
                issues.append(DateIssue(sentence=sent, found_date=d.isoformat()))
                continue

        m = _FULL_DATE_RE.search(sent)
        if m:
            try:
                d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
            except ValueError:
                d = None
            if d and d > as_of:
                issues.append(DateIssue(sentence=sent, found_date=d.isoformat()))
                continue

        m = _BARE_YEAR_RE.search(sent)
        if m:
            year = int(m.group(1))
            if year > as_of.year:
                issues.append(DateIssue(sentence=sent, found_date=str(year)))

    return issues
