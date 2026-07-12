"""Pillar 3 Phase 1 — Part 2: Filing Diff Engine.

Pure computation engine for 10-K/10-Q change detection.
Compares filing sections paragraph-by-paragraph to identify what changed.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from html.parser import HTMLParser


class ChangeClassification(StrEnum):
    SUBSTANTIVE = "SUBSTANTIVE"
    BOILERPLATE = "BOILERPLATE"
    # The downstream count branches in ``classify_filing_diff`` check for
    # ``"NUMERICAL"`` (no _ONLY suffix). Keep the enum value consistent so
    # the per-paragraph classification gets counted correctly instead of
    # silently dropping into the else branch.
    NUMERICAL = "NUMERICAL"
    FORMATTING = "FORMATTING"
    # Aggregate/section-level states used by ``SectionDiffResult.classification``
    # (not returned by ``classify_change``, which only classifies a single
    # paragraph pair).
    STRUCTURAL = "STRUCTURAL"
    MIXED = "MIXED"
    UNCHANGED = "UNCHANGED"


# ── Section Key Definitions ──────────────────────────────────────────────

SECTION_KEYS = {
    "ITEM_1": "Business Description",
    "ITEM_1A": "Risk Factors",
    "ITEM_7": "Management's Discussion and Analysis",
    "ITEM_7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "ITEM_8_NOTES": "Financial Statement Notes",
}

# Patterns for matching section headers in EDGAR 10-K HTML
_SECTION_PATTERNS: dict[str, list[re.Pattern]] = {
    "ITEM_1A": [
        re.compile(r"(?i)item\s+1a[\.\s:\u2014\u2013\-]+\s*risk\s+factors"),
        re.compile(r"(?i)ITEM\s+1A"),
    ],
    "ITEM_1": [
        re.compile(r"(?i)item\s+1[\.\s:\u2014\u2013\-]+\s*business(?!\s+relationships)"),
        re.compile(r"(?i)item\s+1\b(?!\s*a)"),
    ],
    "ITEM_7A": [
        re.compile(r"(?i)item\s+7a[\.\s:\u2014\u2013\-]+\s*quantitative"),
    ],
    "ITEM_7": [
        re.compile(r"(?i)item\s+7[\.\s:\u2014\u2013\-]+\s*management"),
        re.compile(r"(?i)item\s+7\b(?!\s*a)"),
    ],
    "ITEM_8_NOTES": [
        re.compile(r"(?i)item\s+8[\.\s:\u2014\u2013\-]+\s*financial\s+statements"),
        re.compile(r"(?i)notes\s+to\s+(?:consolidated\s+)?financial\s+statements"),
    ],
}

# Boilerplate legal phrases — changes to these are NOT substantive
BOILERPLATE_PHRASES = [
    "forward-looking statements",
    "safe harbor",
    "private securities litigation reform act",
    "actual results may differ materially",
    "risk factors described",
    "incorporated by reference",
    "filed as exhibit",
    "we undertake no obligation",
    "undue reliance",
    "cautionary statement",
    "these forward-looking statements",
    "as of the date of this",
    "annual report on form 10-k",
    "quarterly report on form 10-q",
    "securities and exchange commission",
    "registered under the securities act",
    "exchange act of 1934",
    "sarbanes-oxley act",
    "internal control over financial reporting",
    "principal executive officer",
    "principal financial officer",
    "registrant's telephone number",
    "state of incorporation",
    "commission file number",
    "irs employer identification",
    "fiscal year ended",
    "documents incorporated by reference",
]

# Numerical patterns in filing text
NUMERICAL_PATTERNS = [
    re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?"),
    re.compile(r"\d+(?:\.\d+)?%"),
    re.compile(r"(?:fiscal|calendar)\s+(?:year\s+)?\d{4}"),
    re.compile(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}"),
    re.compile(r"\d{1,2}/\d{1,2}/\d{4}"),
]


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


# ── Core Functions ────────────────────────────────────────────────────────


def extract_sections(html_text: str, filing_type: str = "10-K") -> dict[str, str]:
    """Parse 10-K/10-Q HTML into sections by Item number.

    Handles EDGAR format variations:
    - HTML table-of-contents navigation
    - Various heading formats (bold, caps, tagged)
    - Nested item numbering

    Parameters
    ----------
    html_text : str
        Raw HTML of the 10-K or 10-Q filing.
    filing_type : str
        Filing type ("10-K" or "10-Q").

    Returns
    -------
    dict[str, str]
        Mapping of section_key → cleaned section text.
    """
    plain = _strip_html(html_text)

    # Gather every candidate header position for each section key.
    candidates: dict[str, list[int]] = {}
    for key, patterns in _SECTION_PATTERNS.items():
        starts: set[int] = set()
        for pat in patterns:
            for match in pat.finditer(plain):
                starts.add(match.start())
        if starts:
            candidates[key] = sorted(starts)

    # Global sorted list of all header positions, used to score how much text
    # follows each candidate before the next header of any section.
    all_positions = sorted({p for starts in candidates.values() for p in starts})

    def _span_after(pos: int) -> int:
        for p in all_positions:
            if p > pos:
                return p - pos
        return len(plain) - pos

    # For each section key pick the occurrence with the largest following span.
    # A real body header is followed by the full section text; a table-of-contents
    # entry is immediately followed by the next TOC entry (tiny span), so this
    # discriminator selects the body header over dense TOC links.
    boundaries: list[tuple[str, int]] = []
    for key, starts in candidates.items():
        best_start = max(starts, key=_span_after)
        boundaries.append((key, best_start))

    # Sort boundaries by position
    boundaries.sort(key=lambda x: x[1])

    # Extract text between boundaries
    sections: dict[str, str] = {}
    for i, (key, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(plain)
        section_text = plain[start:end].strip()
        # Remove the section header itself (first line)
        lines = section_text.split("\n", 1)
        text = lines[1].strip() if len(lines) > 1 else ""
        if text:
            sections[key] = _clean_text(text)

    return sections


def _clean_text(text: str) -> str:
    """Normalize whitespace in extracted text."""
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_paragraphs(text: str, min_length: int = 50) -> list[str]:
    """Split section text into meaningful paragraphs.

    Filters out empty lines, very short fragments, and table artifacts.

    Parameters
    ----------
    text : str
        Section text to split.
    min_length : int
        Minimum character length for a paragraph to be included.

    Returns
    -------
    list[str]
        List of paragraph strings.
    """
    # Split on double newlines (paragraph boundaries)
    raw_paragraphs = re.split(r"\n\s*\n", text)

    paragraphs: list[str] = []
    for para in raw_paragraphs:
        cleaned = para.strip()
        # Skip short fragments (likely table artifacts, headers, etc.)
        if len(cleaned) < min_length:
            continue
        # Skip lines that are mostly numbers/symbols (table data)
        alpha_ratio = sum(1 for c in cleaned if c.isalpha()) / max(len(cleaned), 1)
        if alpha_ratio < 0.4:
            continue
        paragraphs.append(cleaned)

    return paragraphs


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Word-level Jaccard index for quick screening.

    J(A, B) = |A ∩ B| / |A ∪ B|

    Parameters
    ----------
    text_a, text_b : str
        Texts to compare.

    Returns
    -------
    float
        Jaccard similarity (0.0 to 1.0).
    """
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a and not words_b:
        return 1.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union) if union else 0.0


def word_overlap_similarity(text_a: str, text_b: str) -> float:
    """Detailed word overlap similarity.

    Overlap(A, B) = |A ∩ B| / min(|A|, |B|)

    More tolerant of paragraphs with different lengths than Jaccard.

    Returns
    -------
    float
        Overlap coefficient (0.0 to 1.0).
    """
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    min_size = min(len(words_a), len(words_b))

    return len(intersection) / min_size if min_size else 0.0


class AlignmentType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


@dataclass
class ParagraphAlignment:
    """Result of aligning a single paragraph."""

    type: AlignmentType
    old_text: str | None = None
    new_text: str | None = None
    old_idx: int | None = None
    new_idx: int | None = None
    similarity: float = 0.0


def align_paragraphs(
    old_paras: list[str],
    new_paras: list[str],
    jaccard_threshold: float = 0.2,
    match_threshold: float = 0.6,
) -> list[ParagraphAlignment]:
    """Two-pass paragraph alignment between old and new sections.

    Pass 1: Jaccard screening — find candidate matches (threshold > 0.2)
    Pass 2: Detailed word overlap for candidates — confirm matches (> 0.6)

    Parameters
    ----------
    old_paras : list[str]
        Paragraphs from the older filing.
    new_paras : list[str]
        Paragraphs from the newer filing.
    jaccard_threshold : float
        Minimum Jaccard similarity to consider as candidate match.
    match_threshold : float
        Minimum word overlap to confirm as a match (MODIFIED or UNCHANGED).

    Returns
    -------
    list[ParagraphAlignment]
        Aligned paragraphs with type: ADDED, REMOVED, MODIFIED, or UNCHANGED.
    """
    results: list[ParagraphAlignment] = []
    matched_old: set[int] = set()
    matched_new: set[int] = set()

    # Pass 1 + 2: Find best match for each old paragraph in new paragraphs
    match_pairs: list[tuple[int, int, float]] = []
    for i, old_p in enumerate(old_paras):
        best_j: int | None = None
        best_sim: float = 0.0
        for j, new_p in enumerate(new_paras):
            # Cheap screening
            jacc = jaccard_similarity(old_p, new_p)
            if jacc < jaccard_threshold:
                continue
            # Detailed comparison
            sim = word_overlap_similarity(old_p, new_p)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j is not None and best_sim >= match_threshold:
            match_pairs.append((i, best_j, best_sim))

    # Sort by similarity descending, resolve conflicts (greedy)
    match_pairs.sort(key=lambda x: -x[2])
    for i, j, sim in match_pairs:
        if i in matched_old or j in matched_new:
            continue
        matched_old.add(i)
        matched_new.add(j)

        if sim >= 0.95:
            results.append(ParagraphAlignment(
                type=AlignmentType.UNCHANGED, old_text=old_paras[i], new_text=new_paras[j],
                old_idx=i, new_idx=j, similarity=sim,
            ))
        elif sim >= match_threshold:
            results.append(ParagraphAlignment(
                type=AlignmentType.MODIFIED, old_text=old_paras[i], new_text=new_paras[j],
                old_idx=i, new_idx=j, similarity=sim,
            ))
        # else: too different, treat as removed + added separately

    # Unmatched old → REMOVED
    for i, para in enumerate(old_paras):
        if i not in matched_old:
            results.append(ParagraphAlignment(
                type=AlignmentType.REMOVED, old_text=para, old_idx=i,
            ))

    # Unmatched new → ADDED
    for j, para in enumerate(new_paras):
        if j not in matched_new:
            results.append(ParagraphAlignment(
                type=AlignmentType.ADDED, new_text=para, new_idx=j,
            ))

    return results


def _is_boilerplate_change(old_text: str, new_text: str) -> bool:
    """Check if the change is just boilerplate legal language.

    A change is boilerplate if:
    1. The text contains at least one recognized boilerplate phrase, AND
    2. The words that actually changed are predominantly boilerplate vocabulary
       (common legal/regulatory filler words, not business-specific terms).
    """
    old_lower = old_text.lower()
    new_lower = new_text.lower()

    # Check if either text contains boilerplate phrases
    combined = old_lower + " " + new_lower
    has_boilerplate_context = any(
        phrase in combined for phrase in BOILERPLATE_PHRASES
    )

    if not has_boilerplate_context:
        return False

    # Find words that actually changed
    old_words = set(old_lower.split())
    new_words = set(new_lower.split())
    changed_words = (old_words - new_words) | (new_words - old_words)

    if not changed_words:
        return True

    # Build a set of all words that appear in any boilerplate phrase
    boilerplate_words: set[str] = set()
    for phrase in BOILERPLATE_PHRASES:
        boilerplate_words.update(phrase.split())
    # Add common legal filler words
    boilerplate_words.update({
        "the", "a", "an", "of", "to", "in", "for", "and", "or", "by",
        "with", "as", "at", "on", "from", "under", "pursuant", "act",
        "1995", "1933", "1934", "section", "defined", "provisions",
    })

    # Check if changed words are predominantly boilerplate vocabulary
    boilerplate_hits = sum(1 for w in changed_words if w in boilerplate_words)
    return boilerplate_hits >= len(changed_words) * 0.6


def _strip_numbers(text: str) -> str:
    """Remove numerical patterns and standalone numbers from text.

    Handles hyphenated compound terms like "3-month" or "10-year": the
    trailing hyphen is consumed along with the digits so the result is the
    clean word ("month", "year") rather than a dangling "-month"/"-year"
    artifact. Leaving the hyphen behind would turn a hyphen-prefixed word
    into a token that no longer matches its un-hyphenated counterpart
    elsewhere in the text, corrupting the numbers-only comparison.
    """
    result = text
    for pat in NUMERICAL_PATTERNS:
        result = pat.sub("", result)
    # Also strip standalone numbers, including a trailing hyphen used in
    # compound terms (e.g. "3-month" -> "month", not "-month").
    result = re.sub(r"\b\d[\d,.]*-?\b", "", result)
    return re.sub(r"\s+", " ", result).strip()


def _is_numerical_only_change(old_text: str, new_text: str) -> bool:
    """Check if only numbers/dates changed between old and new text."""
    stripped_old = _strip_numbers(old_text)
    stripped_new = _strip_numbers(new_text)

    # If texts are the same after removing numbers, only numbers changed
    return jaccard_similarity(stripped_old, stripped_new) > 0.95


def classify_change(
    old_text: str | None,
    new_text: str | None,
    section_key: str,
) -> ChangeClassification:
    """Classify a paragraph change.

    Returns
    -------
    ChangeClassification
        One of: SUBSTANTIVE, BOILERPLATE, NUMERICAL, FORMATTING
    """
    if old_text is None or new_text is None:
        return ChangeClassification.SUBSTANTIVE  # Added or removed paragraphs are substantive

    if not old_text.strip() or not new_text.strip():
        return ChangeClassification.FORMATTING

    # Check for boilerplate changes first
    if _is_boilerplate_change(old_text, new_text):
        return ChangeClassification.BOILERPLATE

    # Check for numerical-only changes
    if _is_numerical_only_change(old_text, new_text):
        return ChangeClassification.NUMERICAL

    # Everything else is substantive
    return ChangeClassification.SUBSTANTIVE


@dataclass
class SectionDiffResult:
    """Result of diffing a single filing section."""

    section_key: str
    section_name: str = ""
    change_pct: float = 0.0
    total_paragraphs_old: int = 0
    total_paragraphs_new: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0
    substantive_count: int = 0
    boilerplate_count: int = 0
    numerical_count: int = 0
    structural_count: int = 0
    classification: ChangeClassification = ChangeClassification.UNCHANGED
    materiality: str = "LOW"
    added_paragraphs: list[dict] = field(default_factory=list)
    removed_paragraphs: list[dict] = field(default_factory=list)
    modified_paragraphs: list[dict] = field(default_factory=list)


def compute_section_diff(
    old_section: str,
    new_section: str,
    section_key: str,
) -> SectionDiffResult:
    """Full section-level diff computation.

    Parameters
    ----------
    old_section : str
        Text of the section from the older filing.
    new_section : str
        Text of the section from the newer filing.
    section_key : str
        Section identifier (e.g., "ITEM_1A").

    Returns
    -------
    SectionDiffResult
        Complete diff results with change counts, classifications, and paragraph details.
    """
    result = SectionDiffResult(
        section_key=section_key,
        section_name=SECTION_KEYS.get(section_key, section_key),
    )

    old_paras = split_paragraphs(old_section)
    new_paras = split_paragraphs(new_section)

    result.total_paragraphs_old = len(old_paras)
    result.total_paragraphs_new = len(new_paras)

    if not old_paras and not new_paras:
        result.classification = ChangeClassification.UNCHANGED
        return result

    # Align paragraphs
    alignments = align_paragraphs(old_paras, new_paras)

    # Classify each change
    for alignment in alignments:
        change_type = alignment.type

        if change_type == AlignmentType.UNCHANGED:
            result.unchanged_count += 1
            continue

        if change_type == AlignmentType.ADDED:
            classification = classify_change(None, alignment.new_text, section_key)
            result.added_count += 1
            result.added_paragraphs.append({
                "text": alignment.new_text,
                "classification": classification,
            })
        elif change_type == AlignmentType.REMOVED:
            classification = classify_change(alignment.old_text, None, section_key)
            result.removed_count += 1
            result.removed_paragraphs.append({
                "text": alignment.old_text,
                "classification": classification,
            })
        elif change_type == AlignmentType.MODIFIED:
            classification = classify_change(
                alignment.old_text, alignment.new_text, section_key,
            )
            result.modified_count += 1
            result.modified_paragraphs.append({
                "old_text": alignment.old_text,
                "new_text": alignment.new_text,
                "similarity": round(alignment.similarity, 4),
                "classification": classification,
            })
        else:
            classification = ChangeClassification.STRUCTURAL

        # Count by classification
        if classification == ChangeClassification.SUBSTANTIVE:
            result.substantive_count += 1
        elif classification == ChangeClassification.BOILERPLATE:
            result.boilerplate_count += 1
        elif classification == ChangeClassification.NUMERICAL:
            result.numerical_count += 1
        elif classification == ChangeClassification.STRUCTURAL:
            result.structural_count += 1

    # Compute change percentage
    total_paras = max(result.total_paragraphs_old, result.total_paragraphs_new, 1)
    changed = result.added_count + result.removed_count + result.modified_count
    result.change_pct = round((changed / total_paras) * 100, 2)

    # Overall classification — majority wins, or MIXED
    counts: dict[ChangeClassification, int] = {
        ChangeClassification.SUBSTANTIVE: result.substantive_count,
        ChangeClassification.BOILERPLATE: result.boilerplate_count,
        ChangeClassification.NUMERICAL: result.numerical_count,
        ChangeClassification.STRUCTURAL: result.structural_count,
    }
    if changed == 0:
        result.classification = ChangeClassification.UNCHANGED
    else:
        max_class = max(counts, key=counts.get)  # type: ignore[arg-type]
        if counts[max_class] > changed * 0.6:
            result.classification = max_class
        else:
            result.classification = ChangeClassification.MIXED

    # Materiality assessment
    result.materiality = _assess_section_materiality(
        section_key, result.change_pct, result.substantive_count,
    )

    return result


def _assess_section_materiality(
    section_key: str,
    change_pct: float,
    substantive_count: int,
) -> str:
    """Assess materiality of section changes.

    Rules:
    - CRITICAL: Risk factors (ITEM_1A) with >= 3 substantive changes
    - HIGH: >20% change OR >= 2 substantive changes
    - MEDIUM: >10% change OR >= 1 substantive change
    - LOW: Mostly boilerplate/numerical
    """
    if section_key == "ITEM_1A" and substantive_count >= 3:
        return "CRITICAL"
    if change_pct > 20.0 or substantive_count >= 2:
        return "HIGH"
    if change_pct > 10.0 or substantive_count >= 1:
        return "MEDIUM"
    return "LOW"


@dataclass
class FilingDiffResult:
    """Result of diffing all sections of two filing versions."""

    overall_materiality: str = "LOW"
    section_diffs: dict[str, SectionDiffResult] = field(default_factory=dict)
    new_sections_added: list[str] = field(default_factory=list)
    sections_removed: list[str] = field(default_factory=list)
    summary_stats: dict = field(default_factory=dict)


def compute_filing_diff(
    old_sections: dict[str, str],
    new_sections: dict[str, str],
) -> FilingDiffResult:
    """Diff all sections of two filing versions.

    Parameters
    ----------
    old_sections : dict[str, str]
        Section texts from the older filing {section_key: text}.
    new_sections : dict[str, str]
        Section texts from the newer filing {section_key: text}.

    Returns
    -------
    FilingDiffResult
        Complete diff with per-section results and overall summary.
    """
    result = FilingDiffResult()

    all_keys = set(old_sections.keys()) | set(new_sections.keys())

    total_changes = 0
    total_substantive = 0
    materialities: list[str] = []

    for key in sorted(all_keys):
        old_text = old_sections.get(key, "")
        new_text = new_sections.get(key, "")

        if key not in old_sections:
            result.new_sections_added.append(key)
            materialities.append("HIGH")
            continue

        if key not in new_sections:
            result.sections_removed.append(key)
            materialities.append("HIGH")
            continue

        section_diff = compute_section_diff(old_text, new_text, key)
        result.section_diffs[key] = section_diff
        materialities.append(section_diff.materiality)
        total_changes += section_diff.added_count + section_diff.removed_count + section_diff.modified_count
        total_substantive += section_diff.substantive_count

    # Overall materiality = max of all section materialities
    priority = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if materialities:
        result.overall_materiality = max(materialities, key=lambda m: priority.get(m, 0))
    else:
        result.overall_materiality = "LOW"

    result.summary_stats = {
        "total_sections_compared": len(result.section_diffs),
        "total_changes": total_changes,
        "total_substantive": total_substantive,
        "new_sections": len(result.new_sections_added),
        "removed_sections": len(result.sections_removed),
    }

    return result
