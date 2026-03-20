"""Entity name and address normalization for resolution matching (Spec 3.5)."""

import re
import unicodedata
import logging
from typing import Any

from metaphone import doublemetaphone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Corporate suffixes to strip during matching (ordered longest-first patterns)
# ---------------------------------------------------------------------------
CORPORATE_SUFFIXES: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bincorporated\b",
        r"\bcorporation\b",
        r"\bcompany\b",
        r"\blimited\b",
        r"\bholdings?\b",
        r"\benterprises?\b",
        r"\binternational\b",
        r"\bgroup\b",
        r"\binc\.?\b",
        r"\bcorp\.?\b",
        r"\bco\.?\b",
        r"\bltd\.?\b",
        r"\bllc\b",
        r"\bllp\b",
        r"\blp\b",
        r"\bplc\b",
        r"\bnv\b",
        r"\bse\b",
        r"\bag\b",
        r"\bgmbh\b",
        r"\bsa\b",
        r"\bsas\b",
        r"\bsrl\b",
        r"\bna\b",
        r"\bab\b",
        r"\bbv\b",
        r"\bpty\b",
        r"\bthe\b",
        r"\b&\b",
        r"\band\b",
    ]
]

# Common address abbreviation expansions
_ADDRESS_ABBREVIATIONS: dict[str, str] = {
    "st": "street",
    "st.": "street",
    "ave": "avenue",
    "ave.": "avenue",
    "blvd": "boulevard",
    "blvd.": "boulevard",
    "dr": "drive",
    "dr.": "drive",
    "ln": "lane",
    "ln.": "lane",
    "rd": "road",
    "rd.": "road",
    "ct": "court",
    "ct.": "court",
    "pl": "place",
    "pl.": "place",
    "ste": "suite",
    "ste.": "suite",
    "apt": "apartment",
    "apt.": "apartment",
    "fl": "floor",
    "fl.": "floor",
    "n": "north",
    "n.": "north",
    "s": "south",
    "s.": "south",
    "e": "east",
    "e.": "east",
    "w": "west",
    "w.": "west",
}

# Pre-compiled whitespace collapser
_MULTI_SPACE = re.compile(r"\s+")

# Non-alphanumeric (keep spaces)
_NON_ALPHANUM = re.compile(r"[^a-z0-9\s]")


def normalize_name(name: str) -> str:
    """Normalize an entity name for matching.

    Pipeline:
        1. Unicode NFKD decomposition — strip combining marks (accents).
        2. Lowercase.
        3. Remove all punctuation except alphanumerics and spaces.
        4. Collapse multiple spaces into one and strip edges.

    Returns the normalized string, or an empty string if *name* is empty/None.
    """
    if not name:
        return ""

    # Unicode decomposition — strip accent marks
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    text = text.lower()
    text = _NON_ALPHANUM.sub(" ", text)
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def strip_suffixes(name: str) -> str:
    """Remove common corporate suffixes (Inc, Corp, LLC, etc.) from *name*.

    Expects an already-normalized name (lowercase, no punctuation).  Applies
    each suffix pattern in order, then collapses whitespace again.
    """
    if not name:
        return ""

    result = name
    for pattern in CORPORATE_SUFFIXES:
        result = pattern.sub(" ", result)

    return _MULTI_SPACE.sub(" ", result).strip()


def phonetic_key(name: str) -> tuple[str, str]:
    """Generate Double Metaphone encoding for *name*.

    The input should be a normalized, suffix-stripped name for best results.
    Returns ``(primary_key, alternate_key)`` — the alternate may be an empty
    string if there is no secondary encoding.
    """
    if not name:
        return ("", "")

    # doublemetaphone returns a 2-tuple of (primary, secondary)
    primary, alternate = doublemetaphone(name)
    return (primary or "", alternate or "")


def normalize_address(address: dict[str, Any] | None) -> dict[str, Any] | None:
    """Standardize address components for comparison.

    Expects a dict with optional keys: ``street``, ``city``, ``state``,
    ``postal_code``, ``country``.  Returns a new dict with every text field
    lowercased, whitespace-collapsed, and common abbreviations expanded.
    Returns ``None`` if the input is ``None`` or empty.
    """
    if not address:
        return None

    normalized: dict[str, Any] = {}

    for key in ("street", "city", "state", "postal_code", "country"):
        raw = address.get(key)
        if raw is None:
            continue

        value = str(raw).strip().lower()
        value = _MULTI_SPACE.sub(" ", value)

        # Expand abbreviations for street-level fields
        if key == "street":
            tokens = value.split()
            tokens = [_ADDRESS_ABBREVIATIONS.get(tok, tok) for tok in tokens]
            value = " ".join(tokens)

        # Strip non-alphanumeric characters from postal codes
        if key == "postal_code":
            value = re.sub(r"[^a-z0-9]", "", value)

        # Country codes should be uppercase ISO-3166 alpha-2
        if key == "country":
            value = value.upper()

        normalized[key] = value

    return normalized if normalized else None
