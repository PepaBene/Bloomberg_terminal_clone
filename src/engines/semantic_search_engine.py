"""Pillar 3 Phase 4B — Semantic Search Engine.

Pure computation engine for document chunking, similarity ranking,
entity extraction, and search response assembly.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime


# ── Dataclasses ────────────────────────────────────────────────────────


@dataclass
class DocumentChunk:
    """A single chunk of a source document."""

    source_type: str
    source_id: str
    title: str
    author: str
    date: str
    chunk_text: str
    chunk_index: int
    metadata: dict | None = None


@dataclass
class SearchResult:
    """A ranked search result."""

    rank: int
    relevance_score: float
    chunk: DocumentChunk
    contextual_summary: str | None = None
    entity_mentions: dict | None = None


@dataclass
class SearchSynthesis:
    """AI synthesis of search results."""

    answer: str
    key_themes: list[str]
    confidence: float
    data_gaps: list[str]


@dataclass
class SemanticSearchResult:
    """Complete search response."""

    query: str
    results: list[SearchResult]
    synthesis: SearchSynthesis | None = None
    follow_ups: list[str] = field(default_factory=list)
    execution_time_ms: int | None = None


# ── 1. Document Chunking ──────────────────────────────────────────────


def chunk_document(
    text: str,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
) -> list[str]:
    """Split text into paragraph-aware chunks respecting token limits.

    Parameters
    ----------
    text : str
        The full document text.
    max_tokens : int
        Maximum approximate token count per chunk (word-based estimate).
    overlap_tokens : int
        Number of overlap tokens between consecutive chunks.

    Returns
    -------
    list[str]
        Ordered list of text chunks.
    """
    if not text or not text.strip():
        return []

    # Split into paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_words: list[str] = []

    for para in paragraphs:
        para_words = para.split()
        # If adding this paragraph exceeds the limit, flush current chunk
        if current_words and len(current_words) + len(para_words) > max_tokens:
            chunks.append(" ".join(current_words))
            # Keep overlap from the end
            if overlap_tokens > 0 and len(current_words) > overlap_tokens:
                current_words = current_words[-overlap_tokens:]
            else:
                current_words = []
        current_words.extend(para_words)

    # Flush remaining
    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ── 2. Document Metadata Extraction ──────────────────────────────────


def extract_document_metadata(text: str, title: str) -> dict:
    """Extract structured metadata from document text.

    Identifies company tickers ($AAPL), financial metrics,
    and date references.

    Parameters
    ----------
    text : str
        Document text.
    title : str
        Document title.

    Returns
    -------
    dict
        {tickers, financial_metrics, dates, word_count}
    """
    if not text:
        return {"tickers": [], "financial_metrics": [], "dates": [], "word_count": 0}

    # Extract $TICKER patterns
    tickers = sorted(set(re.findall(r"\$([A-Z]{1,5})", text)))

    # Extract financial metric mentions
    metric_patterns = [
        "revenue", "earnings", "ebitda", "eps", "margin", "growth",
        "debt", "cash flow", "fcf", "capex", "dividend", "yield",
        "p/e", "ev/ebitda", "roe", "roa", "roic",
    ]
    found_metrics = []
    text_lower = text.lower()
    for m in metric_patterns:
        if m in text_lower:
            found_metrics.append(m)

    # Extract date-like patterns (YYYY, Q1-Q4 YYYY, Month YYYY)
    year_matches = re.findall(r"\b(20[0-9]{2})\b", text)
    quarter_matches = re.findall(r"(Q[1-4]\s*20[0-9]{2})", text, re.IGNORECASE)
    dates = sorted(set(quarter_matches + year_matches))

    return {
        "tickers": tickers,
        "financial_metrics": found_metrics,
        "dates": dates,
        "word_count": len(text.split()),
    }


# ── 3. Cosine Similarity ─────────────────────────────────────────────


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python).

    Parameters
    ----------
    vec_a, vec_b : list[float]
        Vectors of equal length.

    Returns
    -------
    float
        Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero.
    """
    if len(vec_a) != len(vec_b) or len(vec_a) == 0:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


# ── 4. Result Ranking ─────────────────────────────────────────────────


def rank_results(
    query_embedding: list[float],
    doc_embeddings: list[tuple[str, list[float]]],
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Rank documents by similarity to query embedding.

    Parameters
    ----------
    query_embedding : list[float]
        The query vector.
    doc_embeddings : list[tuple[str, list[float]]]
        List of (doc_id, embedding) pairs.
    top_k : int
        Number of top results to return.

    Returns
    -------
    list[tuple[str, float]]
        Sorted list of (doc_id, score) descending by score.
    """
    scored = []
    for doc_id, embedding in doc_embeddings:
        score = compute_cosine_similarity(query_embedding, embedding)
        scored.append((doc_id, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


# ── 5. Recency Reranking ─────────────────────────────────────────────


def rerank_by_recency(
    results: list[dict],
    recency_weight: float = 0.1,
) -> list[dict]:
    """Rerank results by blending relevance score with recency boost.

    Parameters
    ----------
    results : list[dict]
        Each dict must have 'relevance_score' and 'date' (ISO string or None).
    recency_weight : float
        Weight given to recency factor (0-1).

    Returns
    -------
    list[dict]
        Reranked results with 'adjusted_score' added.
    """
    if not results:
        return []

    now = datetime.now(tz=None)
    reranked = []

    for r in results:
        base_score = r.get("relevance_score", 0.0)
        date_str = r.get("date")
        recency_boost = 0.0

        if date_str:
            try:
                doc_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                days_old = max((now - doc_date.replace(tzinfo=None)).days, 0)
                # Decay: newer = higher boost, max 1.0
                recency_boost = max(0.0, 1.0 - (days_old / 365.0))
            except (ValueError, TypeError):
                pass

        adjusted = base_score * (1 - recency_weight) + recency_boost * recency_weight
        entry = dict(r)
        entry["adjusted_score"] = round(adjusted, 4)
        reranked.append(entry)

    reranked.sort(key=lambda x: -x["adjusted_score"])
    return reranked


# ── 6. Document Type Filter ──────────────────────────────────────────


def filter_by_document_type(
    results: list[dict],
    allowed_types: list[str] | None,
) -> list[dict]:
    """Filter results to only allowed document types.

    Parameters
    ----------
    results : list[dict]
        Each dict should have 'source_type'.
    allowed_types : list[str] | None
        Allowed types. None or empty means no filtering.

    Returns
    -------
    list[dict]
        Filtered results.
    """
    if not allowed_types:
        return results

    allowed_set = {t.lower() for t in allowed_types}
    return [r for r in results if r.get("source_type", "").lower() in allowed_set]


# ── 7. Date Range Filter ─────────────────────────────────────────────


def filter_by_date_range(
    results: list[dict],
    start_date: str | None,
    end_date: str | None,
) -> list[dict]:
    """Filter results by publish date range.

    Parameters
    ----------
    results : list[dict]
        Each dict should have 'date' (ISO string).
    start_date : str | None
        Inclusive start date (YYYY-MM-DD).
    end_date : str | None
        Inclusive end date (YYYY-MM-DD).

    Returns
    -------
    list[dict]
        Filtered results.
    """
    if not start_date and not end_date:
        return results

    filtered = []
    for r in results:
        date_str = r.get("date")
        if not date_str:
            continue
        try:
            doc_date = date_str[:10]  # YYYY-MM-DD
            if start_date and doc_date < start_date:
                continue
            if end_date and doc_date > end_date:
                continue
            filtered.append(r)
        except (ValueError, TypeError):
            continue

    return filtered


# ── 8. Entity Mention Extraction ─────────────────────────────────────


def extract_entity_mentions(text: str) -> dict:
    """Extract company, sector, and metric mentions from text.

    Parameters
    ----------
    text : str
        Text to analyze.

    Returns
    -------
    dict
        {companies: [], sectors: [], metrics: []}
    """
    if not text:
        return {"companies": [], "sectors": [], "metrics": []}

    # Companies: $TICKER patterns
    companies = sorted(set(re.findall(r"\$([A-Z]{1,5})", text)))

    # Sectors via keyword matching
    sector_keywords = {
        "technology": "Technology",
        "healthcare": "Healthcare",
        "financials": "Financials",
        "financial": "Financials",
        "energy": "Energy",
        "consumer": "Consumer",
        "industrial": "Industrials",
        "materials": "Materials",
        "utilities": "Utilities",
        "real estate": "Real Estate",
        "telecom": "Communication Services",
        "communication": "Communication Services",
    }
    text_lower = text.lower()
    sectors = sorted({
        label for keyword, label in sector_keywords.items()
        if keyword in text_lower
    })

    # Financial metrics
    metric_patterns = [
        "revenue", "earnings", "ebitda", "eps", "margin",
        "p/e", "ev/ebitda", "roe", "roa", "roic", "fcf",
        "dividend", "yield", "growth", "debt",
    ]
    metrics = sorted({m for m in metric_patterns if m in text_lower})

    return {
        "companies": companies,
        "sectors": sectors,
        "metrics": metrics,
    }


# ── 9. Search Prompt Assembly ────────────────────────────────────────


def assemble_search_prompt(
    query: str,
    top_results: list[dict],
) -> dict:
    """Build an LLM prompt for synthesizing search results.

    Parameters
    ----------
    query : str
        The user's search query.
    top_results : list[dict]
        Top ranked results with 'title', 'chunk_text', 'source_type'.

    Returns
    -------
    dict
        {system_message, user_message, context_snippets: list}
    """
    snippets = []
    for i, r in enumerate(top_results[:5], 1):
        title = r.get("title", "Untitled")
        source = r.get("source_type", "unknown")
        text = r.get("chunk_text", "")[:500]
        snippets.append({
            "rank": i,
            "title": title,
            "source_type": source,
            "excerpt": text,
        })

    system_message = (
        "You are a Bloomberg financial research assistant. "
        "Synthesize the following search results to answer the user's query. "
        "Cite sources by rank number. Identify key themes and data gaps."
    )

    context_text = "\n\n".join(
        f"[{s['rank']}] ({s['source_type']}) {s['title']}:\n{s['excerpt']}"
        for s in snippets
    )

    user_message = f"Query: {query}\n\nSearch Results:\n{context_text}"

    return {
        "system_message": system_message,
        "user_message": user_message,
        "context_snippets": snippets,
    }


# ── 10. Build Search Response ────────────────────────────────────────


def build_search_response(
    query: str,
    ranked_results: list[dict],
    synthesis: dict | None = None,
) -> SemanticSearchResult:
    """Assemble the final search response object.

    Parameters
    ----------
    query : str
        The original query.
    ranked_results : list[dict]
        Ranked results with keys: source_type, source_id, title, author,
        date, chunk_text, chunk_index, relevance_score, metadata.
    synthesis : dict | None
        Optional synthesis with keys: answer, key_themes, confidence, data_gaps.

    Returns
    -------
    SemanticSearchResult
        Complete search result object.
    """
    results: list[SearchResult] = []
    for i, r in enumerate(ranked_results, 1):
        chunk = DocumentChunk(
            source_type=r.get("source_type", "unknown"),
            source_id=r.get("source_id", ""),
            title=r.get("title", ""),
            author=r.get("author", ""),
            date=r.get("date", ""),
            chunk_text=r.get("chunk_text", ""),
            chunk_index=r.get("chunk_index", 0),
            metadata=r.get("metadata"),
        )
        entity_mentions = extract_entity_mentions(r.get("chunk_text", ""))
        results.append(SearchResult(
            rank=i,
            relevance_score=r.get("relevance_score", 0.0),
            chunk=chunk,
            contextual_summary=r.get("contextual_summary"),
            entity_mentions=entity_mentions if any(entity_mentions.values()) else None,
        ))

    synth = None
    if synthesis:
        synth = SearchSynthesis(
            answer=synthesis.get("answer", ""),
            key_themes=synthesis.get("key_themes", []),
            confidence=synthesis.get("confidence", 0.0),
            data_gaps=synthesis.get("data_gaps", []),
        )

    # Generate follow-up suggestions based on the query
    follow_ups = _generate_search_follow_ups(query, results)

    return SemanticSearchResult(
        query=query,
        results=results,
        synthesis=synth,
        follow_ups=follow_ups,
    )


def _generate_search_follow_ups(
    query: str,
    results: list[SearchResult],
) -> list[str]:
    """Generate follow-up search suggestions."""
    follow_ups: list[str] = []

    # Suggest drilling into mentioned companies
    all_companies: set[str] = set()
    for r in results:
        if r.entity_mentions and r.entity_mentions.get("companies"):
            all_companies.update(r.entity_mentions["companies"])

    for ticker in sorted(all_companies)[:3]:
        follow_ups.append(f"What is the latest analysis on ${ticker}?")

    if not follow_ups:
        follow_ups.append(f"Show me more details about: {query}")

    return follow_ups[:5]
