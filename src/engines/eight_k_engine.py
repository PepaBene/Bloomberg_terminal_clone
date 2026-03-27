"""Pillar 3 Phase 1 — Part 3: 8-K Event Engine.

Pure computation engine for 8-K filing event processing.
Classifies items by priority, extracts monetary figures / dates / people,
generates event summaries, and assesses materiality.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser


# ── Priority & Description Maps ──────────────────────────────────────────

PRIORITY_MAP = {
    # Priority 1 — Immediate Alert
    "2.01": 1,  # Completion of acquisition/disposition
    "2.02": 1,  # Results of operations (earnings)
    "2.05": 1,  # Costs of exit/disposal
    "2.06": 1,  # Material impairment
    "4.02": 1,  # Non-reliance on prior statements (RESTATEMENT)
    "5.02": 1,  # CEO/CFO departure/appointment
    # Priority 2 — Same-Day Alert
    "1.01": 2,  # Entry into material agreement
    "1.02": 2,  # Termination of material agreement
    "2.03": 2,  # Creation of direct financial obligation (new debt)
    "2.04": 2,  # Triggering events (covenant breach)
    "3.01": 2,  # Notice of delisting
    "5.01": 2,  # Change of directors
    "5.07": 2,  # Shareholder vote results
    # Priority 3 — Daily Digest
    "7.01": 3,  # Regulation FD disclosure
    "8.01": 3,  # Other events
    "9.01": 3,  # Financial statements and exhibits
}

ITEM_DESCRIPTIONS = {
    "1.01": "Entry Into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate or Increase an Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy Listing Standards",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}


# ── HTML Text Extraction ─────────────────────────────────────────────────


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags, keep text content."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip = True
        if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(html_text: str) -> str:
    """Remove HTML tags, keep text content."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html_text)
    return extractor.get_text()


# ── Regex Patterns ───────────────────────────────────────────────────────

# Monetary figures: $X million, $X billion, $X,XXX, $X.X million, etc.
_MONETARY_PATTERNS = [
    # $500 million, $1.2 billion, $3.5 thousand
    re.compile(
        r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|thousand)",
        re.IGNORECASE,
    ),
    # Plain dollar amounts: $50,000 or $1,234,567.89
    re.compile(
        r"\$\s*([\d,]+(?:\.\d+)?)\b(?!\s*(?:million|billion|thousand))",
        re.IGNORECASE,
    ),
]

_MULTIPLIERS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}

# Date patterns
_DATE_PATTERNS = [
    # Month DD, YYYY  (e.g. March 15, 2024)
    re.compile(
        r"((?:January|February|March|April|May|June|July|August|September"
        r"|October|November|December)\s+\d{1,2},?\s+\d{4})"
    ),
    # MM/DD/YYYY
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})"),
    # YYYY-MM-DD
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]

_DATE_PARSE_FORMATS = [
    "%B %d, %Y",   # March 15, 2024
    "%B %d %Y",    # March 15 2024
    "%m/%d/%Y",    # 03/15/2024
    "%Y-%m-%d",    # 2024-03-15
]

# People patterns
_PEOPLE_PATTERNS = [
    # "John Smith has been appointed as Chief Executive Officer"
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)"
        r"\s+has\s+been\s+appointed\s+(?:as\s+)?(.+?)(?:\.|,|$)",
        re.MULTILINE,
    ),
    # "Jane Doe has resigned as Chief Financial Officer"
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)"
        r"\s+has\s+resigned\s+(?:as\s+|from\s+(?:the\s+position\s+of\s+|her\s+position\s+as\s+|his\s+position\s+as\s+)?)?(.+?)(?:\.|,|$)",
        re.MULTILINE,
    ),
    # "John Smith has been terminated as VP of Operations"
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)"
        r"\s+has\s+been\s+terminated\s+(?:as\s+)?(.+?)(?:\.|,|$)",
        re.MULTILINE,
    ),
    # "The Board appointed John Smith as CEO"
    re.compile(
        r"appointed\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)"
        r"\s+as\s+(.+?)(?:\.|,|$)",
        re.MULTILINE,
    ),
]

# Item header pattern inside 8-K HTML
_ITEM_HEADER_PATTERN = re.compile(
    r"Item\s+(\d+\.\d+)\b",
    re.IGNORECASE,
)


# ── Core Functions ───────────────────────────────────────────────────────


def classify_priority(item_number: str) -> int:
    """Look up the alert priority for an 8-K item number.

    Parameters
    ----------
    item_number : str
        8-K item number, e.g. "2.01", "5.02".

    Returns
    -------
    int
        Priority level: 1 (immediate), 2 (same-day), 3 (daily digest).
        Defaults to 3 for unrecognised items.
    """
    return PRIORITY_MAP.get(item_number, 3)


def get_item_description(item_number: str) -> str:
    """Return a human-readable description for an 8-K item number.

    Parameters
    ----------
    item_number : str
        8-K item number.

    Returns
    -------
    str
        Description string, or "Unknown Item" if not found.
    """
    return ITEM_DESCRIPTIONS.get(item_number, "Unknown Item")


def _get_context_sentence(text: str, match_start: int, match_end: int) -> str:
    """Extract the sentence surrounding a regex match."""
    # Walk backwards to find sentence start
    start = match_start
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
    # Walk forwards to find sentence end
    end = match_end
    while end < len(text) and text[end] not in ".!?\n":
        end += 1
    return text[start:end].strip()


def extract_monetary_figures(text: str) -> list[dict]:
    """Extract dollar amounts from text.

    Handles patterns such as:
    - ``$500 million`` -> 500_000_000
    - ``$1.2 billion`` -> 1_200_000_000
    - ``$50,000``      -> 50_000

    Parameters
    ----------
    text : str
        Filing text to search.

    Returns
    -------
    list[dict]
        Each dict contains:
        - amount_raw (str): The matched text.
        - amount_normalized (float): Numeric value.
        - currency (str): Always "USD".
        - context_sentence (str): Surrounding sentence.
    """
    results: list[dict] = []

    # Pattern 1: $X million/billion/thousand
    for match in _MONETARY_PATTERNS[0].finditer(text):
        raw_number = match.group(1).replace(",", "")
        multiplier_word = match.group(2).lower()
        base = float(raw_number)
        normalised = base * _MULTIPLIERS[multiplier_word]
        results.append({
            "amount_raw": match.group(0).strip(),
            "amount_normalized": normalised,
            "currency": "USD",
            "context_sentence": _get_context_sentence(text, match.start(), match.end()),
        })

    # Pattern 2: plain dollar amounts (no multiplier word)
    for match in _MONETARY_PATTERNS[1].finditer(text):
        raw_number = match.group(1).replace(",", "")
        normalised = float(raw_number)
        results.append({
            "amount_raw": match.group(0).strip(),
            "amount_normalized": normalised,
            "currency": "USD",
            "context_sentence": _get_context_sentence(text, match.start(), match.end()),
        })

    return results


def extract_key_dates(text: str) -> list[dict]:
    """Extract dates from text in common SEC filing formats.

    Supported formats:
    - ``March 15, 2024``
    - ``03/15/2024``
    - ``2024-03-15``

    Parameters
    ----------
    text : str
        Filing text to search.

    Returns
    -------
    list[dict]
        Each dict contains:
        - date_str (str): The matched date text.
        - date_parsed (str | None): ISO-formatted date, or None if parse fails.
        - label (str): Format label (e.g. "month_name", "slash", "iso").
        - context (str): Surrounding sentence.
    """
    results: list[dict] = []
    labels = ["month_name", "slash", "iso"]

    for idx, pattern in enumerate(_DATE_PATTERNS):
        for match in pattern.finditer(text):
            date_str = match.group(1)
            parsed = _try_parse_date(date_str)
            results.append({
                "date_str": date_str,
                "date_parsed": parsed,
                "label": labels[idx],
                "context": _get_context_sentence(text, match.start(), match.end()),
            })

    return results


def _try_parse_date(date_str: str) -> str | None:
    """Attempt to parse a date string into ISO format."""
    for fmt in _DATE_PARSE_FORMATS:
        try:
            dt = datetime.strptime(date_str.replace(",", ""), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_key_people(text: str) -> list[dict]:
    """Extract people and their roles from management-change language.

    Recognises patterns such as:
    - ``[Name] has been appointed as [Role]``
    - ``[Name] has resigned as [Role]``
    - ``[Name] has been terminated as [Role]``

    Parameters
    ----------
    text : str
        Filing text to search.

    Returns
    -------
    list[dict]
        Each dict contains:
        - name (str): Person's name.
        - role (str): Title / position.
        - action (str): "appointed", "resigned", or "terminated".
    """
    results: list[dict] = []
    seen_names: set[str] = set()

    action_keywords = ["appointed", "resigned", "terminated", "appointed"]

    for idx, pattern in enumerate(_PEOPLE_PATTERNS):
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            role = match.group(2).strip()
            action = action_keywords[idx]

            # Deduplicate by name
            if name in seen_names:
                continue
            seen_names.add(name)

            results.append({
                "name": name,
                "role": role,
                "action": action,
            })

    return results


def generate_event_summary(
    entity_name: str,
    item_number: str,
    item_text: str,
    monetary: list[dict] | None = None,
    people: list[dict] | None = None,
    dates: list[dict] | None = None,
) -> str:
    """Generate a template-based 2-3 sentence event summary.

    Parameters
    ----------
    entity_name : str
        Company name (e.g. "Apple Inc.").
    item_number : str
        8-K item number.
    item_text : str
        Raw text of the item (used for fallback).
    monetary : list[dict] | None
        Output of ``extract_monetary_figures``.
    people : list[dict] | None
        Output of ``extract_key_people``.
    dates : list[dict] | None
        Output of ``extract_key_dates``.

    Returns
    -------
    str
        Human-readable event summary.
    """
    monetary = monetary or []
    people = people or []
    dates = dates or []

    description = get_item_description(item_number)
    priority = classify_priority(item_number)

    priority_labels = {1: "IMMEDIATE", 2: "SAME-DAY", 3: "DAILY DIGEST"}
    priority_label = priority_labels.get(priority, "DAILY DIGEST")

    # Management change (Item 5.02)
    if item_number == "5.02" and people:
        person = people[0]
        summary = (
            f"{entity_name} reported a management change ({description}). "
            f"{person['name']} {person['action']} as {person['role']}."
        )
        if len(people) > 1:
            summary += f" {len(people) - 1} additional personnel change(s) were also disclosed."
        summary += f" Alert priority: {priority_label}."
        return summary

    # Acquisition / Disposition (Item 2.01)
    if item_number == "2.01":
        summary = f"{entity_name} disclosed {description.lower()}."
        if monetary:
            amount = monetary[0]
            summary += f" The transaction involves {amount['amount_raw']}."
        if dates:
            summary += f" Key date: {dates[0]['date_str']}."
        summary += f" Alert priority: {priority_label}."
        return summary

    # Restatement (Item 4.02)
    if item_number == "4.02":
        summary = (
            f"{entity_name} issued a notice of {description.lower()}. "
            f"This indicates previously issued financial statements should not be relied upon."
        )
        summary += f" Alert priority: {priority_label}."
        return summary

    # Default template
    summary = f"{entity_name} filed an 8-K disclosing {description.lower()}."
    if monetary:
        summary += f" Monetary figure(s) referenced: {monetary[0]['amount_raw']}."
    if people:
        summary += f" Key person(s): {people[0]['name']}."
    summary += f" Alert priority: {priority_label}."
    return summary


def assess_event_materiality(
    item_number: str,
    monetary: list[dict] | None = None,
    text: str = "",
) -> str:
    """Assess the materiality level of an 8-K event.

    Rules
    -----
    - CRITICAL: Item 4.02 (restatement) always critical, or any item with
      monetary figures exceeding $1 billion.
    - HIGH: Priority 1 items, or monetary figures exceeding $100 million.
    - MEDIUM: Priority 2 items.
    - LOW: Priority 3 items (daily digest).

    Parameters
    ----------
    item_number : str
        8-K item number.
    monetary : list[dict] | None
        Output of ``extract_monetary_figures``.
    text : str
        Raw item text (reserved for future keyword analysis).

    Returns
    -------
    str
        One of "LOW", "MEDIUM", "HIGH", "CRITICAL".
    """
    monetary = monetary or []
    priority = classify_priority(item_number)

    # Restatement is always critical
    if item_number == "4.02":
        return "CRITICAL"

    # Check for very large monetary amounts
    max_amount = 0.0
    for m in monetary:
        if m["amount_normalized"] > max_amount:
            max_amount = m["amount_normalized"]

    if max_amount >= 1_000_000_000:
        return "CRITICAL"

    if max_amount >= 100_000_000:
        return "HIGH"

    # Fall back to priority-based assessment
    if priority == 1:
        return "HIGH"
    if priority == 2:
        return "MEDIUM"
    return "LOW"


def parse_eight_k_items(html_text: str) -> list[dict]:
    """Extract individual items from 8-K filing HTML.

    Scans for ``Item X.XX`` headers and captures the text between
    consecutive headers.

    Parameters
    ----------
    html_text : str
        Raw HTML of the 8-K filing.

    Returns
    -------
    list[dict]
        Each dict contains:
        - item_number (str): e.g. "2.01".
        - item_text (str): Cleaned text for that item section.
    """
    plain = _strip_html(html_text)

    # Find all item header positions
    boundaries: list[tuple[str, int]] = []
    for match in _ITEM_HEADER_PATTERN.finditer(plain):
        item_num = match.group(1)
        # Only keep recognised item numbers (or at least valid format)
        boundaries.append((item_num, match.start()))

    if not boundaries:
        return []

    # Extract text between boundaries
    items: list[dict] = []
    for i, (item_num, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(plain)
        section_text = plain[start:end].strip()

        # Remove the header line itself
        lines = section_text.split("\n", 1)
        text = lines[1].strip() if len(lines) > 1 else ""

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()

        if text:
            items.append({
                "item_number": item_num,
                "item_text": text,
            })

    return items
