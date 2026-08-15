"""Pillar 3 Phase 1 — Part 7: News Entity Linking Engine.

Pure computation engine for linking news articles to entities.
Cascading resolution: ticker → CIK/CUSIP → exact name → alias → fuzzy.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# E-035: fuzzy-match similarity floor, tunable without a code change via
# NEWS_ENTITY_LINKER_FUZZY_THRESHOLD (falls back to this default when unset
# or unparseable).
DEFAULT_FUZZY_THRESHOLD = 0.85


def _resolve_fuzzy_threshold() -> float:
    raw = os.environ.get("NEWS_ENTITY_LINKER_FUZZY_THRESHOLD")
    if not raw:
        return DEFAULT_FUZZY_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_FUZZY_THRESHOLD


# ── Entity Mention Dataclass ──────────────────────────────────────────────


@dataclass
class EntityMention:
    """A resolved entity mention in text."""

    entity_id: str
    mention_text: str
    relevance_score: float  # PRIMARY=1.0, SECONDARY=0.5, PERIPHERAL=0.2
    confidence: float  # 0.0 to 1.0
    is_primary: bool = False
    match_type: str = ""  # ticker, cik, exact_name, alias, fuzzy
    position: int = 0  # character offset in text


# ── Ticker Extraction ─────────────────────────────────────────────────────

# Patterns for ticker mentions
_TICKER_PATTERNS = [
    re.compile(r"\$([A-Z]{1,5})\b"),  # $AAPL
    re.compile(r"\((?:NASDAQ|NYSE|AMEX|OTC):\s*([A-Z]{1,5})\)"),  # (NASDAQ: AAPL)
    re.compile(r"\b(?:ticker|symbol)\s+([A-Z]{1,5})\b", re.IGNORECASE),  # ticker AAPL
]


def extract_ticker_mentions(text: str) -> list[dict]:
    """Extract ticker symbol mentions from text.

    Patterns: $AAPL, (NASDAQ: AAPL), ticker AAPL

    Returns
    -------
    list[dict]
        Each: {ticker, position, confidence}
    """
    results: list[dict] = []
    seen: set[str] = set()

    for pattern in _TICKER_PATTERNS:
        for match in pattern.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in seen:
                seen.add(ticker)
                results.append({
                    "ticker": ticker,
                    "position": match.start(),
                    "confidence": 0.99,
                })

    return results


# ── Identifier Extraction ─────────────────────────────────────────────────

_CIK_PATTERN = re.compile(r"\bCIK\s*[#:]?\s*(\d{7,10})\b", re.IGNORECASE)
_CUSIP_PATTERN = re.compile(r"\bCUSIP\s*[#:]?\s*([A-Z0-9]{9})\b", re.IGNORECASE)
_ISIN_PATTERN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")


def extract_identifiers(text: str) -> list[dict]:
    """Extract CIK, CUSIP, ISIN identifiers from text.

    Returns
    -------
    list[dict]
        Each: {type, value, position, confidence}
    """
    results: list[dict] = []

    for match in _CIK_PATTERN.finditer(text):
        results.append({
            "type": "CIK",
            "value": match.group(1),
            "position": match.start(),
            "confidence": 1.0,
        })

    for match in _CUSIP_PATTERN.finditer(text):
        results.append({
            "type": "CUSIP",
            "value": match.group(1).upper(),
            "position": match.start(),
            "confidence": 1.0,
        })

    for match in _ISIN_PATTERN.finditer(text):
        results.append({
            "type": "ISIN",
            "value": match.group(1),
            "position": match.start(),
            "confidence": 1.0,
        })

    return results


# ── Name Matching ─────────────────────────────────────────────────────────


def exact_name_match(
    text: str,
    entity_names: dict[str, str],
) -> list[dict]:
    """Match exact legal entity names in text.

    Parameters
    ----------
    text : str
        Article text to search.
    entity_names : dict[str, str]
        Mapping of {legal_name_lower: entity_id}.

    Returns
    -------
    list[dict]
        Each: {entity_id, mention_text, position, confidence}
    """
    results: list[dict] = []
    text_lower = text.lower()

    for name_lower, entity_id in entity_names.items():
        if len(name_lower) < 3:
            continue  # Skip very short names to avoid false matches
        idx = text_lower.find(name_lower)
        if idx >= 0:
            results.append({
                "entity_id": entity_id,
                "mention_text": text[idx : idx + len(name_lower)],
                "position": idx,
                "confidence": 0.95,
                "match_type": "exact_name",
            })

    return results


def alias_match(
    text: str,
    entity_aliases: dict[str, str],
) -> list[dict]:
    """Match entity aliases (short names, DBA names) in text.

    Parameters
    ----------
    text : str
        Article text to search.
    entity_aliases : dict[str, str]
        Mapping of {alias_lower: entity_id}.

    Returns
    -------
    list[dict]
        Each: {entity_id, mention_text, position, confidence}
    """
    results: list[dict] = []
    text_lower = text.lower()

    for alias_lower, entity_id in entity_aliases.items():
        if len(alias_lower) < 3:
            continue
        idx = text_lower.find(alias_lower)
        if idx >= 0:
            results.append({
                "entity_id": entity_id,
                "mention_text": text[idx : idx + len(alias_lower)],
                "position": idx,
                "confidence": 0.90,
                "match_type": "alias",
            })

    return results


def _simple_ratio(a: str, b: str) -> float:
    """Simple character-level similarity ratio (no external deps).

    Uses sequence matching: 2 * |common| / (|a| + |b|)
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Count common characters (order-preserving)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    matches = 0
    used = set()
    for c in shorter:
        for j, d in enumerate(longer):
            if j not in used and c == d:
                matches += 1
                used.add(j)
                break

    return (2.0 * matches) / (len(a) + len(b))


def fuzzy_match(
    text: str,
    entity_names: dict[str, str],
    threshold: float | None = None,
) -> list[dict]:
    """Fuzzy name matching for entity resolution.

    Extracts capitalized phrases from text and compares against entity names.
    Uses built-in character similarity (or rapidfuzz if available).

    Parameters
    ----------
    text : str
        Article text to search.
    entity_names : dict[str, str]
        Mapping of {name_lower: entity_id}.
    threshold : float | None
        Minimum similarity score (0.0 to 1.0). Defaults to
        NEWS_ENTITY_LINKER_FUZZY_THRESHOLD (env) or DEFAULT_FUZZY_THRESHOLD
        (E-035) when not passed explicitly.

    Returns
    -------
    list[dict]
        Each: {entity_id, mention_text, similarity, position, confidence}
    """
    if threshold is None:
        threshold = _resolve_fuzzy_threshold()

    # Try to use rapidfuzz for better matching
    try:
        from rapidfuzz import fuzz as _fuzz  # type: ignore[import-untyped]
        def _ratio(a: str, b: str) -> float:
            return _fuzz.ratio(a, b) / 100.0
    except ImportError:
        _ratio = _simple_ratio

    results: list[dict] = []
    # Extract capitalized multi-word phrases as candidates
    candidates = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
    # Also try single capitalized words of sufficient length
    candidates += re.findall(r"\b[A-Z][a-z]{4,}\b", text)

    seen_entities: set[str] = set()
    for candidate in candidates:
        candidate_lower = candidate.lower()
        for name_lower, entity_id in entity_names.items():
            if entity_id in seen_entities:
                continue
            sim = _ratio(candidate_lower, name_lower)
            if sim >= threshold:
                seen_entities.add(entity_id)
                idx = text.find(candidate)
                results.append({
                    "entity_id": entity_id,
                    "mention_text": candidate,
                    "similarity": round(sim, 4),
                    "position": max(idx, 0),
                    "confidence": round(0.70 + (sim - threshold) * 0.5, 4),
                    "match_type": "fuzzy",
                })

    return results


# ── News Type Classification ──────────────────────────────────────────────

_NEWS_TYPE_KEYWORDS: dict[str, list[str]] = {
    "EARNINGS_NEWS": [
        "earnings", "eps", "revenue beat", "revenue miss", "earnings beat",
        "earnings miss", "quarterly results", "guidance", "profit",
        "results of operations", "fiscal quarter",
    ],
    "CORPORATE_ACTION": [
        "acquire", "acquisition", "merger", "spin-off", "spinoff", "buyback",
        "repurchase", "ipo", "initial public offering", "tender offer",
        "restructuring", "divestiture", "split",
    ],
    "MANAGEMENT_CHANGE": [
        "ceo", "cfo", "appoint", "resign", "director", "chief executive",
        "chief financial", "board of directors", "departure",
    ],
    "REGULATORY_ACTION": [
        "fda", "sec enforcement", "doj", "ftc", "antitrust", "enforcement action",
        "regulatory approval", "compliance", "investigation", "subpoena",
    ],
    "MACRO_RELEASE": [
        "cpi", "employment", "gdp", "fomc", "rate decision", "non-farm payroll",
        "inflation", "federal reserve", "monetary policy", "interest rate",
    ],
    "INDUSTRY_DEVELOPMENT": [
        "industry", "sector", "demand", "supply chain", "market share",
        "competitive landscape", "industry-wide", "across the sector",
    ],
    "ANALYSIS_COMMENTARY": [
        "opinion", "analysis", "analyst", "outlook", "forecast", "prediction",
        "commentary", "our view", "we believe", "we expect",
    ],
    "BREAKING_ALERT": [
        "breaking", "urgent", "bankruptcy", "fraud", "restatement", "default",
        "delisting", "crash", "collapse",
    ],
}


def classify_news_type(title: str, text: str) -> str:
    """Keyword-based news type classification.

    Returns one of: BREAKING_ALERT, EARNINGS_NEWS, CORPORATE_ACTION,
    MANAGEMENT_CHANGE, REGULATORY_ACTION, MACRO_RELEASE,
    INDUSTRY_DEVELOPMENT, ANALYSIS_COMMENTARY, PRESS_RELEASE, OTHER
    """
    combined = (title + " " + text).lower()

    # Score each type by keyword matches
    scores: dict[str, int] = {}
    for news_type, keywords in _NEWS_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[news_type] = score

    if not scores:
        return "OTHER"

    # BREAKING_ALERT takes priority if multiple keywords match
    if scores.get("BREAKING_ALERT", 0) >= 2:
        return "BREAKING_ALERT"

    return max(scores, key=scores.get)  # type: ignore[arg-type]


# ── Topic Classification ──────────────────────────────────────────────────

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "M_AND_A": ["acquire", "acquisition", "merger", "takeover", "bid"],
    "RESTRUCTURING": ["restructuring", "cost cutting", "layoff", "downsizing", "reorganization"],
    "PRODUCT_LAUNCH": ["launch", "new product", "unveil", "introduce", "release"],
    "PRODUCT_RECALL": ["recall", "safety issue", "defect", "withdrawal"],
    "LEGAL_ACTION": ["lawsuit", "litigation", "sue", "settlement", "class action"],
    "REGULATORY_APPROVAL": ["fda approval", "regulatory approval", "clearance", "authorized"],
    "MANAGEMENT_CHANGE": ["ceo", "cfo", "appoint", "resign", "departure", "successor"],
    "EARNINGS": ["earnings", "quarterly results", "profit", "revenue", "eps"],
    "DIVIDEND": ["dividend", "payout", "distribution", "special dividend"],
    "BUYBACK": ["buyback", "repurchase", "share repurchase"],
    "DEBT_ISSUANCE": ["bond offering", "debt issuance", "notes offering", "term loan"],
    "CREDIT_EVENT": ["downgrade", "upgrade", "credit rating", "default", "covenant"],
    "PARTNERSHIP": ["partnership", "joint venture", "collaboration", "alliance", "agreement"],
    "CONTRACT_WIN": ["contract award", "contract win", "selected by", "awarded"],
    "CONTRACT_LOSS": ["contract loss", "lost contract", "not renewed", "terminated agreement"],
    "LABOR_ACTION": ["strike", "labor dispute", "union", "walkout", "work stoppage"],
    "ESG_CONTROVERSY": ["environmental", "pollution", "emissions scandal", "governance failure"],
    "CYBERSECURITY": ["cybersecurity", "data breach", "hack", "ransomware", "cyber attack"],
    "PATENT": ["patent", "intellectual property", "ip litigation", "patent infringement"],
    "PRICING": ["price increase", "price cut", "pricing pressure", "price war"],
    "SUPPLY_CHAIN": ["supply chain", "supply disruption", "shortage", "logistics"],
    # §4.7 Pillar-3 follow-through: lets news_enrichment link an article to
    # commodity-price context (src/ai/narratives/commodity.py) the same way
    # SUPPLY_CHAIN/CUSTOMER/etc. already feed propagation -- distinct from
    # SUPPLY_CHAIN's operational-disruption framing (a factory closure vs.
    # an oil/gold/wheat price move).
    "COMMODITY": [
        "commodity price", "oil price", "crude oil", "natural gas price",
        "gold price", "wheat price", "copper price", "opec",
    ],
}


def classify_topics(title: str, text: str) -> list[str]:
    """Multi-label topic classification (keyword-based).

    Returns list of 0-5 matched topic labels.
    """
    combined = (title + " " + text).lower()
    matched: list[tuple[str, int]] = []

    for topic, keywords in _TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            matched.append((topic, score))

    # Return top 5 by keyword match count
    matched.sort(key=lambda x: -x[1])
    return [topic for topic, _ in matched[:5]]


# ── Materiality Assessment ────────────────────────────────────────────────

_CRITICAL_KEYWORDS = [
    "restatement", "non-reliance", "bankruptcy", "fraud", "sec investigation",
    "criminal", "material weakness", "going concern",
]

_HIGH_KEYWORDS = [
    "ceo resign", "cfo resign", "acquisition", "merger", "earnings miss",
    "guidance lower", "downgrade", "default", "delisting",
]


def assess_materiality(
    news_type: str,
    entity_count: int,
    topics: list[str],
    text: str,
) -> str:
    """Assess news article materiality: LOW, MEDIUM, HIGH, CRITICAL.

    Rules:
    - CRITICAL: restatement, fraud, bankruptcy, going concern
    - HIGH: management change (CEO/CFO), M&A, large earnings surprise
    - MEDIUM: corporate action, regulatory, contract
    - LOW: commentary, industry, other
    """
    text_lower = text.lower()

    # CRITICAL keywords
    if any(kw in text_lower for kw in _CRITICAL_KEYWORDS):
        return "CRITICAL"

    # HIGH keywords or priority news types
    if any(kw in text_lower for kw in _HIGH_KEYWORDS):
        return "HIGH"
    if news_type in ("BREAKING_ALERT",):
        return "HIGH"
    if news_type == "MANAGEMENT_CHANGE" and any(
        title in text_lower for title in ("ceo", "cfo", "chief executive", "chief financial")
    ):
        return "HIGH"

    # MEDIUM
    if news_type in ("CORPORATE_ACTION", "REGULATORY_ACTION", "EARNINGS_NEWS"):
        return "MEDIUM"
    if any(t in ("M_AND_A", "LEGAL_ACTION", "CREDIT_EVENT") for t in topics):
        return "MEDIUM"

    return "LOW"


# ── Full Entity Linking Pipeline ──────────────────────────────────────────


def link_entities(
    text: str,
    title: str,
    entity_lookup: dict,
    fuzzy_threshold: float | None = None,
) -> list[EntityMention]:
    """Full cascading entity resolution pipeline.

    Priority order:
    1. Ticker match → 0.99 confidence
    2. CIK/CUSIP/ISIN match → 1.00 confidence
    3. Exact legal name match → 0.95 confidence
    4. Alias match → 0.90 confidence
    5. Fuzzy match → 0.70-0.85 confidence

    Parameters
    ----------
    text : str
        Article body text.
    title : str
        Article title.
    entity_lookup : dict
        Must have keys: tickers ({ticker: entity_id}), ciks ({cik: entity_id}),
        cusips ({cusip: entity_id}), names ({name_lower: entity_id}),
        aliases ({alias_lower: entity_id}).
    fuzzy_threshold : float | None
        Overrides the fuzzy-match similarity floor (E-035). Falls back to
        NEWS_ENTITY_LINKER_FUZZY_THRESHOLD / DEFAULT_FUZZY_THRESHOLD.

    Returns
    -------
    list[EntityMention]
        Deduplicated entity mentions, sorted by confidence descending.
    """
    full_text = title + "\n" + text
    title_lower = title.lower()
    mentions: dict[str, EntityMention] = {}  # entity_id → best mention

    # 1. Ticker match
    tickers = entity_lookup.get("tickers", {})
    for tm in extract_ticker_mentions(full_text):
        entity_id = tickers.get(tm["ticker"])
        if entity_id and entity_id not in mentions:
            mentions[entity_id] = EntityMention(
                entity_id=entity_id,
                mention_text=tm["ticker"],
                relevance_score=_compute_relevance(tm["ticker"].lower(), title_lower, full_text.lower()),
                confidence=0.99,
                match_type="ticker",
                position=tm["position"],
            )

    # 2. CIK/CUSIP/ISIN match
    for identifier in extract_identifiers(full_text):
        lookup_map = entity_lookup.get(f"{identifier['type'].lower()}s", {})
        entity_id = lookup_map.get(identifier["value"])
        if entity_id and entity_id not in mentions:
            mentions[entity_id] = EntityMention(
                entity_id=entity_id,
                mention_text=identifier["value"],
                relevance_score=0.5,
                confidence=1.0,
                match_type="identifier",
                position=identifier["position"],
            )

    # 3. Exact name match
    names = entity_lookup.get("names", {})
    for nm in exact_name_match(full_text, names):
        entity_id = nm["entity_id"]
        if entity_id not in mentions:
            mentions[entity_id] = EntityMention(
                entity_id=entity_id,
                mention_text=nm["mention_text"],
                relevance_score=_compute_relevance(nm["mention_text"].lower(), title_lower, full_text.lower()),
                confidence=0.95,
                match_type="exact_name",
                position=nm["position"],
            )

    # 4. Alias match
    aliases = entity_lookup.get("aliases", {})
    for am in alias_match(full_text, aliases):
        entity_id = am["entity_id"]
        if entity_id not in mentions:
            mentions[entity_id] = EntityMention(
                entity_id=entity_id,
                mention_text=am["mention_text"],
                relevance_score=_compute_relevance(am["mention_text"].lower(), title_lower, full_text.lower()),
                confidence=0.90,
                match_type="alias",
                position=am["position"],
            )

    # 5. Fuzzy match
    for fm in fuzzy_match(full_text, names, threshold=fuzzy_threshold):
        entity_id = fm["entity_id"]
        if entity_id not in mentions:
            mentions[entity_id] = EntityMention(
                entity_id=entity_id,
                mention_text=fm["mention_text"],
                relevance_score=_compute_relevance(fm["mention_text"].lower(), title_lower, full_text.lower()),
                confidence=fm["confidence"],
                match_type="fuzzy",
                position=fm["position"],
            )

    # Set is_primary for the main subject of the article
    result = sorted(mentions.values(), key=lambda m: (-m.confidence, -m.relevance_score))
    if result:
        result[0].is_primary = True

    return result


def _compute_relevance(
    mention_lower: str,
    title_lower: str,
    full_text_lower: str,
) -> float:
    """Compute relevance score for an entity mention.

    PRIMARY (1.0): Entity in title or first paragraph.
    SECONDARY (0.5): Entity in body only.
    PERIPHERAL (0.2): Brief/passing mention.
    """
    if mention_lower in title_lower:
        return 1.0

    # Check if in first 500 characters (roughly first paragraph)
    first_para = full_text_lower[:500]
    if mention_lower in first_para:
        return 1.0

    # Count mentions
    count = full_text_lower.count(mention_lower)
    if count >= 3:
        return 0.5
    return 0.2
