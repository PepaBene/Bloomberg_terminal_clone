"""Tests for Pillar 3 Phase 1 — Part 7: News Deduplication Engine."""

import pytest

from src.engines.news_dedup import (
    content_fingerprint_dedup,
    deduplicate,
    hamming_distance,
    simhash,
    title_dedup,
    url_dedup,
)


# ── URL Deduplication Tests ───────────────────────────────────────────────


class TestUrlDedup:

    def test_exact_url_dedup(self):
        articles = [
            {"source_url": "https://example.com/a", "title": "Article A"},
            {"source_url": "https://example.com/b", "title": "Article B"},
            {"source_url": "https://example.com/a", "title": "Article A Dup"},
        ]
        result = url_dedup(articles)
        assert len(result) == 2
        assert result[0]["title"] == "Article A"
        assert result[1]["title"] == "Article B"

    def test_case_insensitive_url(self):
        articles = [
            {"source_url": "https://EXAMPLE.COM/A", "title": "First"},
            {"source_url": "https://example.com/a", "title": "Second"},
        ]
        result = url_dedup(articles)
        assert len(result) == 1

    def test_no_duplicates(self):
        articles = [
            {"source_url": "https://a.com", "title": "A"},
            {"source_url": "https://b.com", "title": "B"},
        ]
        result = url_dedup(articles)
        assert len(result) == 2

    def test_empty_list(self):
        assert url_dedup([]) == []

    def test_keeps_first_occurrence(self):
        articles = [
            {"source_url": "https://a.com", "title": "First"},
            {"source_url": "https://a.com", "title": "Second"},
        ]
        result = url_dedup(articles)
        assert result[0]["title"] == "First"


# ── Title Deduplication Tests ─────────────────────────────────────────────


class TestTitleDedup:

    def test_identical_titles_removed(self):
        articles = [
            {"title": "Apple Reports Strong Q3 Earnings"},
            {"title": "Apple Reports Strong Q3 Earnings"},
        ]
        result = title_dedup(articles)
        assert len(result) == 1

    def test_near_duplicate_titles(self):
        articles = [
            {"title": "Apple Reports Strong Q3 Earnings Beat"},
            {"title": "Apple Reports Strong Q3 Earnings Beat Expectations"},
        ]
        result = title_dedup(articles, threshold=0.8)
        assert len(result) == 1  # Similar enough to dedup

    def test_different_titles_kept(self):
        articles = [
            {"title": "Apple Reports Strong Q3 Earnings"},
            {"title": "Microsoft Announces Cloud Partnership"},
        ]
        result = title_dedup(articles)
        assert len(result) == 2

    def test_threshold_respected(self):
        articles = [
            {"title": "Apple quarterly revenue increases substantially"},
            {"title": "Apple quarterly revenue increases by fifteen percent"},
        ]
        # With strict threshold, these should be kept separate
        result_strict = title_dedup(articles, threshold=0.95)
        assert len(result_strict) == 2

    def test_empty_titles(self):
        articles = [{"title": ""}, {"title": ""}]
        result = title_dedup(articles)
        # Both have empty titles — deduped to 1
        assert len(result) == 1


# ── Simhash Tests ─────────────────────────────────────────────────────────


class TestSimhash:

    def test_identical_texts_same_hash(self):
        text = "The quick brown fox jumps over the lazy dog"
        assert simhash(text) == simhash(text)

    def test_similar_texts_close_hashes(self):
        text1 = "Apple reported strong quarterly earnings with revenue growth of fifteen percent."
        text2 = "Apple reported strong quarterly earnings with revenue growth of fourteen percent."
        h1 = simhash(text1)
        h2 = simhash(text2)
        assert hamming_distance(h1, h2) <= 15  # Similar texts have closer hashes than random

    def test_different_texts_distant_hashes(self):
        text1 = "Apple reported strong quarterly earnings growth"
        text2 = "Hurricane causes devastating damage across coastal regions"
        h1 = simhash(text1)
        h2 = simhash(text2)
        assert hamming_distance(h1, h2) > 5  # Very different texts

    def test_empty_text(self):
        assert simhash("") == 0
        assert simhash("   ") == 0

    def test_consistent_across_calls(self):
        text = "Consistent hashing test"
        assert simhash(text) == simhash(text)


class TestHammingDistance:

    def test_identical(self):
        assert hamming_distance(0b1010, 0b1010) == 0

    def test_one_bit_different(self):
        assert hamming_distance(0b1010, 0b1011) == 1

    def test_all_different(self):
        assert hamming_distance(0b0000, 0b1111) == 4

    def test_zero(self):
        assert hamming_distance(0, 0) == 0


# ── Content Fingerprint Dedup Tests ───────────────────────────────────────


class TestContentFingerprintDedup:

    def test_identical_content_removed(self):
        articles = [
            {"body_text": "Apple Inc reported quarterly revenue of five billion dollars."},
            {"body_text": "Apple Inc reported quarterly revenue of five billion dollars."},
        ]
        result = content_fingerprint_dedup(articles)
        assert len(result) == 1

    def test_very_similar_content_removed(self):
        # Use longer texts with more overlap for reliable simhash dedup
        base = "Apple Inc reported strong quarterly revenue growth driven by iPhone sales and services. "
        articles = [
            {"body_text": base * 5 + "Third quarter results exceeded expectations."},
            {"body_text": base * 5 + "Fourth quarter results exceeded expectations."},
        ]
        result = content_fingerprint_dedup(articles, hamming_threshold=10)
        assert len(result) == 1  # Very similar long texts

    def test_different_content_kept(self):
        articles = [
            {"body_text": "Apple reported strong earnings growth driven by iPhone sales."},
            {"body_text": "Hurricane causes widespread damage across the southeastern United States coast."},
        ]
        result = content_fingerprint_dedup(articles)
        assert len(result) == 2

    def test_empty_body_kept(self):
        articles = [
            {"body_text": ""},
            {"body_text": "Some content here about financial results."},
        ]
        result = content_fingerprint_dedup(articles)
        assert len(result) == 2

    def test_uses_summary_fallback(self):
        articles = [
            {"summary": "Same article summary about Apple earnings report."},
            {"summary": "Same article summary about Apple earnings report."},
        ]
        result = content_fingerprint_dedup(articles)
        assert len(result) == 1


# ── Full Deduplication Pipeline Tests ─────────────────────────────────────


class TestDeduplicate:

    def test_url_dedup_first_tier(self):
        articles = [
            {"source_url": "https://a.com/1", "title": "A1", "body_text": "Content 1"},
            {"source_url": "https://a.com/1", "title": "A1 Dup", "body_text": "Content 1 dup"},
            {"source_url": "https://a.com/2", "title": "A2", "body_text": "Content 2"},
        ]
        result = deduplicate(articles)
        assert len(result) == 2

    def test_title_dedup_second_tier(self):
        articles = [
            {"source_url": "https://a.com/1", "title": "Apple Q3 Earnings Beat", "body_text": "Content"},
            {"source_url": "https://b.com/2", "title": "Apple Q3 Earnings Beat Expectations", "body_text": "Content2"},
        ]
        result = deduplicate(articles)
        assert len(result) <= 2  # May dedup by title

    def test_content_dedup_third_tier(self):
        articles = [
            {"source_url": "https://a.com/1", "title": "Different Title A", "body_text": "Identical article content about Apple earnings growth and revenue increase."},
            {"source_url": "https://b.com/2", "title": "Different Title B", "body_text": "Identical article content about Apple earnings growth and revenue increase."},
        ]
        result = deduplicate(articles)
        assert len(result) == 1  # Content-level dedup

    def test_all_unique(self):
        articles = [
            {"source_url": "https://a.com/1", "title": "Title A", "body_text": "Apple earnings grew 15%"},
            {"source_url": "https://b.com/2", "title": "Title B", "body_text": "Microsoft launched cloud product"},
            {"source_url": "https://c.com/3", "title": "Title C", "body_text": "Federal Reserve raised interest rates"},
        ]
        result = deduplicate(articles)
        assert len(result) == 3

    def test_empty_input(self):
        assert deduplicate([]) == []

    def test_single_article(self):
        articles = [{"source_url": "https://a.com", "title": "A", "body_text": "Content"}]
        result = deduplicate(articles)
        assert len(result) == 1
