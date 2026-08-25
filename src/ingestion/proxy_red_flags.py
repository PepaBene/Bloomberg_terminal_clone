"""DEF 14A structural governance red-flag text-mining (§4.7 Pillar-3
follow-through -- the gap ``scripts/compute_governance_assessments.py``'s
own docstring named as deliberately not attempted: dual-class shares,
poison pill, staggered board, majority voting, and related-party
transactions all live in DEF 14A prose, not the tabular board/comp/
proposal sections ``src/ingestion/edgar_proxy.py`` already parses.

Same honesty contract as ``edgar_proxy.py``/``edgar_esg.py``: a flag is
only ever set to a definite value (``True`` or ``False``) when the text
actually supports it. Absence of evidence returns ``None`` and the key is
simply omitted by ``mine_structural_red_flags`` -- ``governance_scoring.
py``'s own ``.get(key)`` semantics already treat an absent key as "no
evidence of the negative condition" (except ``has_majority_voting``,
which that engine itself defaults to flagging when unknown, so leaving
it unmined there still produces a *correct*, not fabricated, result).

Pure text functions only -- no I/O. Fetching the proxy body itself reuses
``EdgarProxyConnector._fetch_body``/``_strip_tags``, the same rate-limited
SEC fetch path ``edgar_proxy.py``'s own body-parsing already uses, rather
than a second httpx client duplicating that logic.
"""
from __future__ import annotations

import re

# --- Dual-class share structure ------------------------------------------
# Proxies essentially never explicitly disclaim "we do NOT have a
# dual-class structure" when they don't have one -- it's simply absent
# from the document -- so there's no reliable negative pattern to check
# for this one; only a positive match is meaningful.
_DUAL_CLASS_POSITIVE = re.compile(
    r"\b(?:class\s+[ab]\s+common\s+stock|dual[\s-]class\s+(?:structure|stock|shares)|"
    r"two\s+classes\s+of\s+common\s+stock|unequal\s+voting\s+rights)\b",
    re.IGNORECASE,
)

# --- Poison pill / shareholder rights plan -------------------------------
_POISON_PILL_POSITIVE = re.compile(
    r"\b(?:poison\s+pill|shareholder\s+rights\s+plan|stockholder\s+rights\s+plan|"
    r"rights\s+agreement)\b",
    re.IGNORECASE,
)
_POISON_PILL_NEGATIVE = re.compile(
    r"(?:do\s+not\s+have|does\s+not\s+have|no|not\s+adopted|not\s+maintain)"
    r"[^.]{0,40}(?:poison\s+pill|shareholder\s+rights\s+plan|stockholder\s+rights\s+plan|rights\s+agreement)",
    re.IGNORECASE,
)

# --- Staggered / classified board -----------------------------------------
_STAGGERED_BOARD_POSITIVE = re.compile(
    r"\b(?:staggered\s+board|classified\s+board|three\s+classes\s+of\s+directors|"
    r"divided\s+into\s+(?:three|3)\s+classes)\b",
    re.IGNORECASE,
)
_STAGGERED_BOARD_NEGATIVE = re.compile(
    r"(?:do\s+not\s+have|does\s+not\s+have|not)\s+[^.]{0,40}(?:staggered|classified)\s+board",
    re.IGNORECASE,
)

# --- Majority voting standard for uncontested director elections ---------
# Unlike poison pill/staggered board, a proxy's voting standard is a
# binary choice it states outright (majority vs. plurality) -- so these
# two patterns are treated as mutually informative rather than one being
# "positive" and the other "negative evidence of the positive."
_MAJORITY_VOTING_POSITIVE = re.compile(
    r"\bmajority\s+vot(?:e|ing)\s+standard\b|"
    r"\bmajority\s+voting\s+(?:standard\s+)?(?:for|in)\s+(?:the\s+)?election\s+of\s+directors\b",
    re.IGNORECASE,
)
_PLURALITY_VOTING_POSITIVE = re.compile(
    r"\bplurality\s+vot(?:e|ing)\s+standard\b",
    re.IGNORECASE,
)

# --- Related-party transactions -------------------------------------------
# Item 404 disclosure is a REQUIRED section in nearly every proxy, present
# whether or not there's anything to report -- the section header alone
# is not evidence of a red flag. Only an explicit "none to report" negation
# or a described transaction with a dollar figure counts as a definite
# answer either way.
_RELATED_PARTY_SECTION = re.compile(
    r"related\s+part(?:y|ies)\s+transactions?", re.IGNORECASE,
)
_RELATED_PARTY_NONE = re.compile(
    r"(?:no|none|not\s+aware\s+of\s+any|there\s+(?:were|was|are|is)\s+no)"
    r"[^.]{0,80}related\s+part(?:y|ies)\s+transactions?",
    re.IGNORECASE,
)
_RELATED_PARTY_PRESENT = re.compile(
    r"related\s+part(?:y|ies)\s+transactions?[^.]{0,200}\$[\d,]+",
    re.IGNORECASE,
)


def extract_dual_class(text: str) -> bool | None:
    """``True`` if the proxy body describes a dual-class share structure,
    else ``None`` (no reliable negative pattern exists for this flag)."""
    return True if _DUAL_CLASS_POSITIVE.search(text) else None


def extract_poison_pill(text: str) -> bool | None:
    if _POISON_PILL_NEGATIVE.search(text):
        return False
    if _POISON_PILL_POSITIVE.search(text):
        return True
    return None


def extract_staggered_board(text: str) -> bool | None:
    if _STAGGERED_BOARD_NEGATIVE.search(text):
        return False
    if _STAGGERED_BOARD_POSITIVE.search(text):
        return True
    return None


def extract_majority_voting(text: str) -> bool | None:
    """``True`` when the proxy explicitly describes a majority-voting
    standard for director elections, ``False`` when it explicitly
    describes plurality voting instead, ``None`` when neither is found
    (or, rarely, both -- e.g. majority voting with a plurality carve-out
    for contested elections -- which this heuristic can't disambiguate,
    so it declines to guess rather than pick one)."""
    has_majority = bool(_MAJORITY_VOTING_POSITIVE.search(text))
    has_plurality = bool(_PLURALITY_VOTING_POSITIVE.search(text))
    if has_majority and not has_plurality:
        return True
    if has_plurality and not has_majority:
        return False
    return None


def extract_related_party(text: str) -> bool | None:
    if not _RELATED_PARTY_SECTION.search(text):
        return None
    if _RELATED_PARTY_PRESENT.search(text):
        return True
    if _RELATED_PARTY_NONE.search(text):
        return False
    return None


def mine_structural_red_flags(text: str) -> dict:
    """Combined pass over one proxy body's plain text. Returns only the
    keys ``governance_scoring.py``'s ``detect_red_flags`` understands,
    and only when this text supports a definite answer -- see each
    extractor's own docstring for what "no evidence" means for that
    specific flag.
    """
    out: dict = {}
    for key, value in (
        ("dual_class", extract_dual_class(text)),
        ("has_poison_pill", extract_poison_pill(text)),
        ("has_staggered_board", extract_staggered_board(text)),
        ("has_majority_voting", extract_majority_voting(text)),
        ("related_party_flag", extract_related_party(text)),
    ):
        if value is not None:
            out[key] = value
    return out
