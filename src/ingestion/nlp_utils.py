"""NLP utilities for 10-K relationship extraction (Spec 15.3).

Keyword-based extraction patterns for identifying business relationships
from SEC 10-K filings. Provides:
- Relationship keyword dictionaries (customer, supplier, competitor)
- Revenue percentage regex extraction (ASC 280 >10% customer disclosures)
- 10-K section extraction helpers (Item 1, 1A, 7)
- Entity name fuzzy matching utilities
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relationship keyword patterns
# ---------------------------------------------------------------------------

CUSTOMER_KEYWORDS: list[str] = [
    "customer",
    "customers",
    "client",
    "clients",
    "accounted for",
    "represented",
    "comprised",
    "revenue from",
    "sales to",
    "sold to",
    "major customer",
    "significant customer",
    "largest customer",
    "principal customer",
    "end-user",
    "end user",
    "buyer",
    "purchaser",
]

SUPPLIER_KEYWORDS: list[str] = [
    "supplier",
    "suppliers",
    "vendor",
    "vendors",
    "sourced from",
    "procured from",
    "purchased from",
    "sole source",
    "single source",
    "key supplier",
    "major supplier",
    "principal supplier",
    "raw material",
    "raw materials",
    "supply agreement",
    "supply chain",
    "subcontractor",
    "manufacturer",
    "distributor",
]

COMPETITOR_KEYWORDS: list[str] = [
    "competitor",
    "competitors",
    "compete",
    "competes",
    "competing",
    "competition",
    "competitive",
    "competitive landscape",
    "principal competitor",
    "major competitor",
    "market participant",
    "rival",
    "alternative provider",
]

# ---------------------------------------------------------------------------
# Revenue percentage extraction (ASC 280 disclosures)
# ---------------------------------------------------------------------------

# Patterns like "accounted for approximately 15% of revenue"
# or "represented 12.5 percent of our total net revenue"
_REVENUE_PCT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:accounted\s+for|represented|comprised|constituted|contributed)"
        r"\s+(?:approximately\s+|about\s+|roughly\s+|over\s+|more\s+than\s+)?"
        r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)\s+of\s+"
        r"(?:our\s+)?(?:total\s+)?(?:net\s+)?(?:revenue|sales|net\s+revenue)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:approximately|about|roughly|over|more\s+than)\s+"
        r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)",
        re.IGNORECASE,
    ),
]


def extract_revenue_percentages(text: str) -> list[float]:
    """Extract revenue percentage figures from a text passage.

    Targets ASC 280 disclosures where companies must report customers
    accounting for >10% of revenue.

    Returns a sorted (descending) list of unique percentage values found.
    """
    percentages: set[float] = set()
    for pattern in _REVENUE_PCT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                pct = float(match.group(1))
                if 0.0 < pct <= 100.0:
                    percentages.add(pct)
            except (ValueError, IndexError):
                continue
    return sorted(percentages, reverse=True)


# ---------------------------------------------------------------------------
# 10-K section extraction
# ---------------------------------------------------------------------------

# Section header patterns in 10-K filings
_ITEM_PATTERNS: dict[str, re.Pattern[str]] = {
    "item_1": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*1[.\s:]+\s*(?:Business|BUSINESS)",
        re.IGNORECASE,
    ),
    "item_1a": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*1A[.\s:]+\s*(?:Risk\s*Factors?|RISK\s*FACTORS?)",
        re.IGNORECASE,
    ),
    "item_7": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*7[.\s:]+\s*(?:Management|MANAGEMENT)",
        re.IGNORECASE,
    ),
    "item_7a": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*7A[.\s:]+",
        re.IGNORECASE,
    ),
    "item_2": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*2[.\s:]+",
        re.IGNORECASE,
    ),
    "item_8": re.compile(
        r"(?:^|\n)\s*(?:ITEM|Item)\s*8[.\s:]+",
        re.IGNORECASE,
    ),
}


def extract_10k_section(full_text: str, section: str) -> str | None:
    """Extract a specific section from a 10-K filing text.

    Args:
        full_text: The complete 10-K filing text.
        section: One of 'item_1', 'item_1a', 'item_7'.

    Returns:
        The extracted section text, or None if not found.
    """
    start_pattern = _ITEM_PATTERNS.get(section)
    if start_pattern is None:
        logger.warning("Unknown 10-K section: %s", section)
        return None

    start_match = start_pattern.search(full_text)
    if start_match is None:
        return None

    start_pos = start_match.start()

    # Determine the end boundary — next Item header after the start
    # Map section to the expected next section(s)
    next_sections: dict[str, list[str]] = {
        "item_1": ["item_1a", "item_2"],
        "item_1a": ["item_2"],
        "item_7": ["item_7a", "item_8"],
    }

    end_pos = len(full_text)
    for next_sec in next_sections.get(section, []):
        next_pattern = _ITEM_PATTERNS.get(next_sec)
        if next_pattern:
            next_match = next_pattern.search(full_text, pos=start_pos + 100)
            if next_match:
                end_pos = min(end_pos, next_match.start())
                break

    return full_text[start_pos:end_pos].strip()


# ---------------------------------------------------------------------------
# Entity name matching
# ---------------------------------------------------------------------------


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name for fuzzy matching.

    Strips common suffixes (Inc, Corp, LLC, etc.), lowercases, and removes
    punctuation to enable loose matching between filing text and our entity DB.
    """
    if not name:
        return ""

    cleaned = name.strip().lower()

    # Remove common corporate suffixes
    suffixes = [
        r"\binc\.?\b",
        r"\bcorp\.?\b",
        r"\bcorporation\b",
        r"\bcompany\b",
        r"\bco\.?\b",
        r"\bltd\.?\b",
        r"\bllc\b",
        r"\blimited\b",
        r"\bplc\b",
        r"\bn\.?a\.?\b",
        r"\bgroup\b",
        r"\bholdings?\b",
        r"\binternational\b",
        r"\bintl\.?\b",
        r"\bthe\b",
    ]
    for suffix in suffixes:
        cleaned = re.sub(suffix, "", cleaned)

    # Remove punctuation and extra whitespace
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def entity_names_match(name_a: str, name_b: str) -> bool:
    """Check if two entity names likely refer to the same company.

    Uses normalized comparison. Returns True if the normalized forms
    are equal or one is a substring of the other (for handling partial names).
    """
    norm_a = normalize_entity_name(name_a)
    norm_b = normalize_entity_name(name_b)

    if not norm_a or not norm_b:
        return False

    # Exact match after normalization
    if norm_a == norm_b:
        return True

    # Substring match (one contained in the other)
    if len(norm_a) >= 3 and len(norm_b) >= 3:
        if norm_a in norm_b or norm_b in norm_a:
            return True

    return False


def find_entity_mentions(
    text: str, entity_names: list[str]
) -> list[dict[str, Any]]:
    """Find mentions of known entity names in a text passage.

    Args:
        text: The text to search.
        entity_names: List of entity names to look for.

    Returns:
        List of dicts with keys: name, start, end, context (surrounding text).
    """
    mentions: list[dict[str, Any]] = []
    text_lower = text.lower()

    for name in entity_names:
        if not name or len(name) < 3:
            continue

        # Search for the entity name (case-insensitive, word boundary)
        pattern = re.compile(
            r"\b" + re.escape(name.lower()) + r"\b",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text_lower):
            # Extract surrounding context (100 chars before and after)
            ctx_start = max(0, match.start() - 100)
            ctx_end = min(len(text), match.end() + 100)
            context = text[ctx_start:ctx_end].strip()

            mentions.append({
                "name": name,
                "start": match.start(),
                "end": match.end(),
                "context": context,
            })

    return mentions


def classify_relationship_from_context(context: str) -> str | None:
    """Classify a relationship type based on surrounding text context.

    Args:
        context: Text surrounding an entity mention.

    Returns:
        One of 'CUSTOMER', 'SUPPLIER', 'COMPETITOR', or None if unclear.
    """
    context_lower = context.lower()

    # Score each relationship type
    scores: dict[str, int] = {"CUSTOMER": 0, "SUPPLIER": 0, "COMPETITOR": 0}

    for keyword in CUSTOMER_KEYWORDS:
        if keyword in context_lower:
            scores["CUSTOMER"] += 1

    for keyword in SUPPLIER_KEYWORDS:
        if keyword in context_lower:
            scores["SUPPLIER"] += 1

    for keyword in COMPETITOR_KEYWORDS:
        if keyword in context_lower:
            scores["COMPETITOR"] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return None

    # Return the highest scoring type (ties go to None for ambiguity)
    top_types = [k for k, v in scores.items() if v == max_score]
    if len(top_types) == 1:
        return top_types[0]

    return None
