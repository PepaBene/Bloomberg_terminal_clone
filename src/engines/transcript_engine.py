"""Pillar 3 Phase 2 -- Part 2: Transcript Engine.

Pure computation engine for earnings call transcript processing.
Parses transcript structure, scores tone across sections, detects
hedging/confidence language, counts forward-looking statements, and
tracks buzzword usage.

No database access -- all functions accept and return plain data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.engines.sentiment_analysis import (
    detect_confidence_language,
    detect_hedging_language,
    keyword_sentiment,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORWARD_LOOKING_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bwill\b", re.IGNORECASE),
    re.compile(r"\bexpect\b", re.IGNORECASE),
    re.compile(r"\banticipate\b", re.IGNORECASE),
    re.compile(r"\bproject\b", re.IGNORECASE),
    re.compile(r"\bforecast\b", re.IGNORECASE),
    re.compile(r"\boutlook\b", re.IGNORECASE),
    re.compile(r"\bplan\b", re.IGNORECASE),
    re.compile(r"\btarget\b", re.IGNORECASE),
    re.compile(r"\bguidance\b", re.IGNORECASE),
    re.compile(r"\bintend\b", re.IGNORECASE),
    re.compile(r"\bbelieve\b", re.IGNORECASE),
]

BUZZWORD_DICT: frozenset[str] = frozenset({
    "ai", "machine_learning", "tariff", "trade", "restructuring",
    "cost_reduction", "cloud", "subscription", "inflation", "supply_chain",
    "margin_expansion", "pricing_power", "headcount", "market_share",
    "digital", "sustainability", "synergy",
})

# Regex patterns for matching multi-word buzzwords and their natural forms
_BUZZWORD_PATTERNS: dict[str, re.Pattern] = {
    "ai": re.compile(r"\bai\b|\bartificial intelligence\b", re.IGNORECASE),
    "machine_learning": re.compile(r"\bmachine learning\b", re.IGNORECASE),
    "tariff": re.compile(r"\btariffs?\b", re.IGNORECASE),
    "trade": re.compile(r"\btrade\b", re.IGNORECASE),
    "restructuring": re.compile(r"\brestructuring\b", re.IGNORECASE),
    "cost_reduction": re.compile(r"\bcost reduction\b|\bcost cutting\b", re.IGNORECASE),
    "cloud": re.compile(r"\bcloud\b", re.IGNORECASE),
    "subscription": re.compile(r"\bsubscriptions?\b", re.IGNORECASE),
    "inflation": re.compile(r"\binflation\b|\binflationary\b", re.IGNORECASE),
    "supply_chain": re.compile(r"\bsupply chain\b", re.IGNORECASE),
    "margin_expansion": re.compile(r"\bmargin expansion\b", re.IGNORECASE),
    "pricing_power": re.compile(r"\bpricing power\b", re.IGNORECASE),
    "headcount": re.compile(r"\bheadcount\b", re.IGNORECASE),
    "market_share": re.compile(r"\bmarket share\b", re.IGNORECASE),
    "digital": re.compile(r"\bdigital\b", re.IGNORECASE),
    "sustainability": re.compile(r"\bsustainability\b", re.IGNORECASE),
    "synergy": re.compile(r"\bsynergies?\b", re.IGNORECASE),
}

CEO_TITLE_PATTERNS: re.Pattern = re.compile(
    r"\b(?:chief executive officer|ceo)\b", re.IGNORECASE,
)

CFO_TITLE_PATTERNS: re.Pattern = re.compile(
    r"\b(?:chief financial officer|cfo)\b", re.IGNORECASE,
)

# Speaker line pattern: "Name -- Title" or "Name - Title, Company"
_SPEAKER_PATTERN = re.compile(
    r"^([A-Z][A-Za-z\s\.\-']+?)\s+[-\u2013\u2014]{1,2}\s+(.+)$",
    re.MULTILINE,
)

# Section header patterns
_PREPARED_MARKER = re.compile(
    r"(?:prepared\s+remarks|opening\s+remarks|presentation)", re.IGNORECASE,
)
_QA_MARKER = re.compile(
    r"(?:question[\-\s]*and[\-\s]*answer|q\s*&\s*a|q\s+and\s+a)", re.IGNORECASE,
)

# Common English stopwords for topic extraction
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "ought",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "mine",
    "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
    "am", "not", "no", "nor", "so", "too", "very", "just", "also",
    "than", "then", "now", "here", "there", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "about", "up",
    "out", "on", "off", "over", "under", "again", "further",
    "and", "but", "or", "if", "while", "as", "until", "because",
    "of", "at", "by", "for", "with", "from", "into", "through",
    "during", "before", "after", "above", "below", "to", "in",
    "what", "which", "who", "whom", "whose", "think", "going",
    "well", "really", "much", "get", "got", "like", "one", "two",
    "first", "second", "new", "way", "back", "still", "even",
    "said", "say", "see", "come", "make", "know", "take", "go",
    "good", "year", "quarter", "percent", "million", "billion",
    "thank", "thanks", "question", "answer",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TranscriptSection:
    """A single section of a transcript with speaker information."""

    section_type: str  # "prepared" or "qa"
    speaker: str
    speaker_title: str
    speaker_firm: str
    text: str


@dataclass
class TranscriptStructure:
    """Parsed structure of an earnings call transcript."""

    prepared_remarks: list[TranscriptSection] = field(default_factory=list)
    qa_sections: list[TranscriptSection] = field(default_factory=list)
    ceo_remarks: str = ""
    cfo_remarks: str = ""
    participants: list[dict] = field(default_factory=list)


@dataclass
class TopicAnalysis:
    """Topic comparison between current and prior transcripts."""

    mgmt_topics: list[str] = field(default_factory=list)
    qa_topics: list[str] = field(default_factory=list)
    absent_topics: list[str] = field(default_factory=list)
    new_topics: list[str] = field(default_factory=list)


@dataclass
class TranscriptAnalysis:
    """Full analysis result for an earnings call transcript."""

    overall_tone: float = 0.0
    prepared_tone: float = 0.0
    qa_tone: float = 0.0
    ceo_tone: float = 0.0
    cfo_tone: float = 0.0
    tone_divergence: float = 0.0
    hedging_ratio: float = 0.0
    confidence_ratio: float = 0.0
    forward_looking_pct: float = 0.0
    buzzword_counts: dict[str, int] = field(default_factory=dict)
    topics: TopicAnalysis = field(default_factory=TopicAnalysis)
    sentence_count: int = 0


# ---------------------------------------------------------------------------
# Sentence splitting helper
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by period followed by space or end."""
    if not text or not text.strip():
        return []
    # Split on period + space or period at end of string
    sentences = re.split(r"\.\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------


def extract_transcript_structure(raw_text: str) -> TranscriptStructure:
    """Parse a raw earnings call transcript into structured sections.

    Splits on "Prepared Remarks" / "Question-and-Answer" section markers.
    Within each section, identifies speakers by "Name -- Title" or
    "Name - Title, Company" patterns.  Matches CEO/CFO by title patterns.

    Parameters
    ----------
    raw_text : str
        Full transcript text.

    Returns
    -------
    TranscriptStructure with prepared_remarks, qa_sections, ceo/cfo text,
    and participants list.
    """
    structure = TranscriptStructure()

    if not raw_text or not raw_text.strip():
        return structure

    # Split into prepared vs Q&A blocks
    prepared_text = ""
    qa_text = ""

    prepared_match = _PREPARED_MARKER.search(raw_text)
    qa_match = _QA_MARKER.search(raw_text)

    if prepared_match and qa_match and prepared_match.start() < qa_match.start():
        prepared_text = raw_text[prepared_match.end():qa_match.start()].strip()
        qa_text = raw_text[qa_match.end():].strip()
    elif qa_match:
        # Q&A found but no explicit prepared section -- everything before is prepared
        qa_text = raw_text[qa_match.end():].strip()
        prepared_text = raw_text[:qa_match.start()].strip()
    elif prepared_match:
        # Only prepared section
        prepared_text = raw_text[prepared_match.end():].strip()
    else:
        # No markers -- treat entire text as prepared remarks
        prepared_text = raw_text.strip()

    # Parse speaker blocks from each section
    seen_participants: dict[str, dict] = {}

    def _parse_speaker_blocks(
        text: str, section_type: str,
    ) -> list[TranscriptSection]:
        """Extract speaker blocks from a section of text."""
        sections: list[TranscriptSection] = []
        matches = list(_SPEAKER_PATTERN.finditer(text))

        if not matches:
            # No speakers found -- treat as single anonymous block
            if text.strip():
                sections.append(TranscriptSection(
                    section_type=section_type,
                    speaker="Unknown",
                    speaker_title="",
                    speaker_firm="",
                    text=text.strip(),
                ))
            return sections

        for idx, match in enumerate(matches):
            speaker_name = match.group(1).strip()
            title_and_firm = match.group(2).strip()

            # Separate title from firm (if comma-separated)
            if "," in title_and_firm:
                parts = title_and_firm.rsplit(",", 1)
                speaker_title = parts[0].strip()
                speaker_firm = parts[1].strip()
            else:
                speaker_title = title_and_firm
                speaker_firm = ""

            # Extract speech text up to next speaker
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            speech_text = text[start:end].strip()

            section = TranscriptSection(
                section_type=section_type,
                speaker=speaker_name,
                speaker_title=speaker_title,
                speaker_firm=speaker_firm,
                text=speech_text,
            )
            sections.append(section)

            # Track participant
            if speaker_name not in seen_participants:
                seen_participants[speaker_name] = {
                    "name": speaker_name,
                    "title": speaker_title,
                    "firm": speaker_firm,
                }

        return sections

    structure.prepared_remarks = _parse_speaker_blocks(prepared_text, "prepared")
    structure.qa_sections = _parse_speaker_blocks(qa_text, "qa")

    # Identify CEO/CFO remarks
    ceo_parts: list[str] = []
    cfo_parts: list[str] = []

    for section in structure.prepared_remarks + structure.qa_sections:
        if CEO_TITLE_PATTERNS.search(section.speaker_title):
            ceo_parts.append(section.text)
        elif CFO_TITLE_PATTERNS.search(section.speaker_title):
            cfo_parts.append(section.text)

    structure.ceo_remarks = " ".join(ceo_parts)
    structure.cfo_remarks = " ".join(cfo_parts)

    # Build participants list
    structure.participants = list(seen_participants.values())

    return structure


def compute_tone_scores(structure: TranscriptStructure) -> dict[str, float]:
    """Score sentiment tone for each section of a transcript.

    Uses keyword_sentiment() from sentiment_analysis engine.

    Parameters
    ----------
    structure : TranscriptStructure
        Parsed transcript structure.

    Returns
    -------
    dict with keys: overall, prepared, qa, ceo, cfo, divergence
    """
    # Combine all text for overall
    all_text_parts: list[str] = []
    prepared_text_parts: list[str] = []
    qa_text_parts: list[str] = []

    for sec in structure.prepared_remarks:
        all_text_parts.append(sec.text)
        prepared_text_parts.append(sec.text)

    for sec in structure.qa_sections:
        all_text_parts.append(sec.text)
        qa_text_parts.append(sec.text)

    overall_text = " ".join(all_text_parts)
    prepared_text = " ".join(prepared_text_parts)
    qa_text = " ".join(qa_text_parts)

    overall = keyword_sentiment(overall_text).score
    prepared = keyword_sentiment(prepared_text).score
    qa = keyword_sentiment(qa_text).score
    ceo = keyword_sentiment(structure.ceo_remarks).score
    cfo = keyword_sentiment(structure.cfo_remarks).score

    # Divergence: difference between prepared and Q&A tone
    divergence = round(abs(prepared - qa), 4)

    return {
        "overall": overall,
        "prepared": prepared,
        "qa": qa,
        "ceo": ceo,
        "cfo": cfo,
        "divergence": divergence,
    }


def compute_hedging_ratio(text: str) -> float:
    """Compute the ratio of sentences containing hedging language.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    float
        hedging_sentences / total_sentences (0.0 if no sentences).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return 0.0

    hedging_count = 0
    for sentence in sentences:
        if detect_hedging_language(sentence) > 0:
            hedging_count += 1

    return round(hedging_count / len(sentences), 4)


def compute_confidence_ratio(text: str) -> float:
    """Compute the ratio of sentences containing confidence language.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    float
        confidence_sentences / total_sentences (0.0 if no sentences).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return 0.0

    confidence_count = 0
    for sentence in sentences:
        if detect_confidence_language(sentence) > 0:
            confidence_count += 1

    return round(confidence_count / len(sentences), 4)


def compute_forward_looking_pct(text: str) -> float:
    """Compute the percentage of sentences containing forward-looking language.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    float
        forward_looking_count / total_sentences (0.0 if no sentences).
    """
    sentences = _split_sentences(text)
    if not sentences:
        return 0.0

    forward_count = 0
    for sentence in sentences:
        for pattern in FORWARD_LOOKING_PATTERNS:
            if pattern.search(sentence):
                forward_count += 1
                break  # Count each sentence only once

    return round(forward_count / len(sentences), 4)


def count_buzzwords(text: str) -> dict[str, int]:
    """Count occurrences of each tracked buzzword in text.

    Case-insensitive matching. Multi-word terms (e.g. "supply chain")
    are matched as phrases.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    dict[str, int]
        Mapping of buzzword key to occurrence count.
    """
    if not text or not text.strip():
        return {bw: 0 for bw in sorted(BUZZWORD_DICT)}

    counts: dict[str, int] = {}
    for bw_key in sorted(BUZZWORD_DICT):
        pattern = _BUZZWORD_PATTERNS.get(bw_key)
        if pattern:
            counts[bw_key] = len(pattern.findall(text))
        else:
            counts[bw_key] = 0

    return counts


def extract_topics(text: str, top_n: int = 5) -> list[str]:
    """Extract top N topics from text by word frequency.

    Tokenizes, removes stopwords, counts frequencies, and returns
    the most common terms.

    Parameters
    ----------
    text : str
        Input text.
    top_n : int
        Number of topics to return.

    Returns
    -------
    list[str]
        Top N terms by frequency.
    """
    if not text or not text.strip():
        return []

    # Tokenize: extract words (3+ characters to skip noise)
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())

    # Remove stopwords
    filtered = [w for w in words if w not in _STOPWORDS]

    if not filtered:
        return []

    # Count frequencies
    freq: dict[str, int] = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1

    # Sort by frequency descending, then alphabetically for ties
    sorted_words = sorted(freq.items(), key=lambda x: (-x[1], x[0]))

    return [word for word, _ in sorted_words[:top_n]]


def compare_topics(
    current: list[str], prior: list[str],
) -> tuple[list[str], list[str]]:
    """Compare current and prior topic lists.

    Parameters
    ----------
    current : list[str]
        Topics from current transcript.
    prior : list[str]
        Topics from prior transcript.

    Returns
    -------
    tuple of (absent_topics, new_topics)
        absent_topics: in prior but not current
        new_topics: in current but not prior
    """
    current_set = set(current)
    prior_set = set(prior)

    absent_topics = sorted(prior_set - current_set)
    new_topics = sorted(current_set - prior_set)

    return absent_topics, new_topics


def analyze_transcript(
    raw_text: str,
    prior_topics: list[str] | None = None,
) -> TranscriptAnalysis:
    """Orchestrate full transcript analysis.

    Calls extract_transcript_structure, compute_tone_scores,
    compute_hedging_ratio, compute_confidence_ratio,
    compute_forward_looking_pct, count_buzzwords, and extract_topics.

    Parameters
    ----------
    raw_text : str
        Full transcript text.
    prior_topics : list[str] | None
        Topics from prior quarter for comparison.

    Returns
    -------
    TranscriptAnalysis with all computed metrics.
    """
    if not raw_text or not raw_text.strip():
        return TranscriptAnalysis()

    # Parse structure
    structure = extract_transcript_structure(raw_text)

    # Compute tones
    tones = compute_tone_scores(structure)

    # Combine all text for text-level analysis
    all_text_parts: list[str] = []
    for sec in structure.prepared_remarks:
        all_text_parts.append(sec.text)
    for sec in structure.qa_sections:
        all_text_parts.append(sec.text)
    full_text = " ".join(all_text_parts) if all_text_parts else raw_text

    # Sentence count
    sentences = _split_sentences(full_text)

    # Language ratios
    hedging = compute_hedging_ratio(full_text)
    confidence = compute_confidence_ratio(full_text)
    forward_pct = compute_forward_looking_pct(full_text)

    # Buzzwords
    buzzwords = count_buzzwords(full_text)

    # Topics
    mgmt_text = " ".join(sec.text for sec in structure.prepared_remarks)
    qa_text = " ".join(sec.text for sec in structure.qa_sections)
    mgmt_topics = extract_topics(mgmt_text)
    qa_topics = extract_topics(qa_text)
    all_topics = extract_topics(full_text)

    absent: list[str] = []
    new: list[str] = []
    if prior_topics is not None:
        absent, new = compare_topics(all_topics, prior_topics)

    topics = TopicAnalysis(
        mgmt_topics=mgmt_topics,
        qa_topics=qa_topics,
        absent_topics=absent,
        new_topics=new,
    )

    return TranscriptAnalysis(
        overall_tone=tones["overall"],
        prepared_tone=tones["prepared"],
        qa_tone=tones["qa"],
        ceo_tone=tones["ceo"],
        cfo_tone=tones["cfo"],
        tone_divergence=tones["divergence"],
        hedging_ratio=hedging,
        confidence_ratio=confidence,
        forward_looking_pct=forward_pct,
        buzzword_counts=buzzwords,
        topics=topics,
        sentence_count=len(sentences),
    )
