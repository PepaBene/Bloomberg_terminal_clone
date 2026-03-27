"""Pillar 3 Phase 1 — Part 7: News Deduplication Engine.

Pure computation engine for three-tier news article deduplication:
1. URL-based (exact match)
2. Title similarity (Jaccard > 0.8)
3. Content fingerprint (simhash hamming distance ≤ 3)

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict


# ── URL Deduplication ─────────────────────────────────────────────────────


def url_dedup(articles: list[dict]) -> list[dict]:
    """Remove exact URL duplicates. Keep first occurrence.

    Parameters
    ----------
    articles : list[dict]
        Each must have a 'source_url' key.

    Returns
    -------
    list[dict]
        Deduplicated articles (first seen wins).
    """
    seen_urls: set[str] = set()
    result: list[dict] = []

    for article in articles:
        url = article.get("source_url", "").strip().lower()
        if url and url not in seen_urls:
            seen_urls.add(url)
            result.append(article)
        elif not url:
            # Keep articles without URLs (shouldn't happen but be safe)
            result.append(article)

    return result


# ── Title Deduplication ───────────────────────────────────────────────────


def _jaccard_words(text_a: str, text_b: str) -> float:
    """Word-level Jaccard similarity."""
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


def title_dedup(articles: list[dict], threshold: float = 0.8) -> list[dict]:
    """Remove near-duplicate titles using Jaccard word similarity.

    Keeps the first article when titles are > threshold similar.

    Parameters
    ----------
    articles : list[dict]
        Each must have a 'title' key.
    threshold : float
        Jaccard similarity threshold (default 0.8).

    Returns
    -------
    list[dict]
        Deduplicated articles.
    """
    result: list[dict] = []

    for article in articles:
        title = article.get("title", "")
        is_dup = False
        for kept in result:
            if _jaccard_words(title, kept.get("title", "")) >= threshold:
                is_dup = True
                break
        if not is_dup:
            result.append(article)

    return result


# ── Simhash Content Fingerprinting ────────────────────────────────────────


def simhash(text: str, hash_bits: int = 64) -> int:
    """Compute simhash fingerprint for near-duplicate content detection.

    Algorithm:
    1. Tokenize text into words
    2. Hash each word to a fixed-width integer
    3. For each bit position, sum +1 if bit is 1, -1 if bit is 0
    4. Final hash: bit is 1 if sum is positive, 0 otherwise

    Parameters
    ----------
    text : str
        Input text to fingerprint.
    hash_bits : int
        Number of bits in the hash (default 64).

    Returns
    -------
    int
        Simhash fingerprint.
    """
    if not text or not text.strip():
        return 0

    words = text.lower().split()
    if not words:
        return 0

    # Accumulator for each bit position
    bit_sums = [0] * hash_bits

    for word in words:
        # Hash each word to a consistent integer
        word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)
        for i in range(hash_bits):
            if word_hash & (1 << i):
                bit_sums[i] += 1
            else:
                bit_sums[i] -= 1

    # Build final hash
    fingerprint = 0
    for i in range(hash_bits):
        if bit_sums[i] > 0:
            fingerprint |= (1 << i)

    return fingerprint


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Compute hamming distance between two integer hashes.

    Parameters
    ----------
    hash_a, hash_b : int
        Two simhash fingerprints to compare.

    Returns
    -------
    int
        Number of differing bits.
    """
    xor = hash_a ^ hash_b
    return bin(xor).count("1")


def content_fingerprint_dedup(
    articles: list[dict],
    hamming_threshold: int = 3,
    text_key: str = "body_text",
) -> list[dict]:
    """Remove near-duplicate content by simhash hamming distance.

    Two articles are duplicates if hamming_distance(hash_a, hash_b) <= threshold.

    Parameters
    ----------
    articles : list[dict]
        Each must have a text content key (default 'body_text').
    hamming_threshold : int
        Maximum hamming distance for duplicate detection (default 3).
    text_key : str
        Key to use for text content (default 'body_text').

    Returns
    -------
    list[dict]
        Deduplicated articles.
    """
    result: list[dict] = []
    kept_hashes: list[int] = []

    for article in articles:
        text = article.get(text_key) or article.get("summary", "") or ""
        if not text.strip():
            result.append(article)
            continue

        h = simhash(text)
        is_dup = False
        for kept_h in kept_hashes:
            if hamming_distance(h, kept_h) <= hamming_threshold:
                is_dup = True
                break

        if not is_dup:
            result.append(article)
            kept_hashes.append(h)

    return result


# ── Full Deduplication Pipeline ───────────────────────────────────────────


def deduplicate(articles: list[dict]) -> list[dict]:
    """Three-tier deduplication pipeline.

    1. URL-based exact match removal
    2. Title similarity (Jaccard > 0.8) removal
    3. Content fingerprint (simhash hamming ≤ 3) removal

    Parameters
    ----------
    articles : list[dict]
        Raw article list. Each should have: source_url, title, body_text/summary.

    Returns
    -------
    list[dict]
        Deduplicated article list.
    """
    # Tier 1: URL dedup
    stage1 = url_dedup(articles)

    # Tier 2: Title dedup
    stage2 = title_dedup(stage1, threshold=0.8)

    # Tier 3: Content fingerprint dedup
    stage3 = content_fingerprint_dedup(stage2, hamming_threshold=3)

    return stage3
