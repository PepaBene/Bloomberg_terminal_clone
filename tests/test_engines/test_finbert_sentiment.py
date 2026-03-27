"""Tests for the FinBERT sentiment engine (Pillar 3 Phase 2 -- Part 4).

All tests use keyword fallback (no transformers dependency).
"""

import pytest

from src.engines.finbert_sentiment import (
    FinBERTResult,
    ParagraphSentimentResult,
    EntitySentimentResult,
    RollingAggregation,
    SentimentAnomaly,
    CombinedAnomalyResult,
    score_text,
    score_paragraphs,
    score_entity_specific,
    compute_rolling_aggregation,
    compute_peer_z_score,
    detect_anomalies,
    _keyword_to_finbert_result,
)


# ═══════════════════════════════════════════════════════════════════════════
# TestScoreText
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreText:
    def test_positive_text(self):
        text = "The company reported strong growth and beat expectations with record profits."
        result = score_text(text)
        assert isinstance(result, FinBERTResult)
        assert result.sentiment == "POSITIVE"
        assert result.composite_score > 0
        assert result.positive_prob > result.negative_prob

    def test_negative_text(self):
        text = "Revenue decline and loss led to a downgrade with risk of bankruptcy."
        result = score_text(text)
        assert result.sentiment == "NEGATIVE"
        assert result.composite_score < 0
        assert result.negative_prob > result.positive_prob

    def test_neutral_text(self):
        text = "The board held its scheduled quarterly meeting on Tuesday."
        result = score_text(text)
        assert result.sentiment == "NEUTRAL"
        assert result.neutral_prob > 0

    def test_empty_text(self):
        result = score_text("")
        assert result.sentiment == "NEUTRAL"
        assert result.confidence == 0.0
        assert result.composite_score == 0.0

    def test_confidence_range(self):
        text = "Strong growth, beat expectations, record profits, gains, outperform."
        result = score_text(text)
        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.positive_prob <= 1.0
        assert 0.0 <= result.negative_prob <= 1.0
        assert 0.0 <= result.neutral_prob <= 1.0

    def test_keyword_fallback_method(self):
        """Without transformers, method must be KEYWORD."""
        result = score_text("Good earnings beat today.")
        assert result.method == "KEYWORD"


# ═══════════════════════════════════════════════════════════════════════════
# TestScoreParagraphs
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreParagraphs:
    def test_multiple_paragraphs(self):
        paras = [
            "The company posted strong revenue growth and beat expectations.",
            "However, margins declined significantly with rising risk.",
            "Overall the outlook remains cautiously optimistic with growth.",
        ]
        results = score_paragraphs(paras)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, ParagraphSentimentResult)

    def test_shift_detection(self):
        paras = [
            "Strong growth and record profits. Beat and gains.",
            "Decline loss risk bankruptcy downgrade pessimistic.",
        ]
        results = score_paragraphs(paras)
        assert len(results) == 2
        # First paragraph has no shift (no prior)
        assert results[0].sentiment_shift is False
        # Second paragraph should be different sentiment
        assert results[1].sentiment_shift is True

    def test_single_paragraph(self):
        results = score_paragraphs(["Earnings beat expectations."])
        assert len(results) == 1
        assert results[0].paragraph_index == 0
        assert results[0].sentiment_shift is False

    def test_empty_list(self):
        results = score_paragraphs([])
        assert results == []

    def test_all_same_sentiment(self):
        paras = [
            "Strong growth and positive gains.",
            "Beat expectations with robust momentum.",
            "Outperform with record profit and expansion.",
        ]
        results = score_paragraphs(paras)
        # All should be positive; no shifts after the first
        for r in results[1:]:
            assert r.sentiment_shift is False


# ═══════════════════════════════════════════════════════════════════════════
# TestScoreEntitySpecific
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreEntitySpecific:
    def test_single_entity(self):
        text = "Apple reported strong growth and beat expectations. Google had weak results."
        mentions = {"AAPL": ["Apple"]}
        results = score_entity_specific(text, mentions)
        assert len(results) == 1
        assert results[0].entity_id == "AAPL"
        assert results[0].sentence_count >= 1

    def test_multi_entity(self):
        text = "Apple posted strong growth. Google had a decline and miss. Microsoft was stable."
        mentions = {"AAPL": ["Apple"], "GOOG": ["Google"], "MSFT": ["Microsoft"]}
        results = score_entity_specific(text, mentions)
        assert len(results) == 3
        entity_ids = {r.entity_id for r in results}
        assert "AAPL" in entity_ids
        assert "GOOG" in entity_ids
        assert "MSFT" in entity_ids

    def test_no_mentions(self):
        text = "The market moved sideways today."
        mentions = {"AAPL": ["Apple"]}
        results = score_entity_specific(text, mentions)
        assert results == []

    def test_entity_not_found(self):
        text = "Apple posted strong growth."
        mentions = {"TSLA": ["Tesla"]}
        results = score_entity_specific(text, mentions)
        assert results == []

    def test_mixed_sentiment(self):
        text = (
            "Apple beat earnings and showed strong growth. "
            "Apple also faces risk from declining margins and restructuring."
        )
        mentions = {"AAPL": ["Apple"]}
        results = score_entity_specific(text, mentions)
        assert len(results) == 1
        assert results[0].sentence_count >= 1
        assert -1.0 <= results[0].avg_sentiment <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# TestRollingAggregation
# ═══════════════════════════════════════════════════════════════════════════


class TestRollingAggregation:
    def test_7d_aggregation(self):
        scores = [
            {"sentiment_score": 0.5, "confidence": 0.9, "relevance": 1.0},
            {"sentiment_score": 0.3, "confidence": 0.8, "relevance": 0.7},
            {"sentiment_score": 0.1, "confidence": 0.6, "relevance": 0.5},
        ]
        result = compute_rolling_aggregation(scores, "7D")
        assert result is not None
        assert isinstance(result, RollingAggregation)
        assert result.timeframe == "7D"
        assert result.article_count == 3
        assert result.avg_sentiment > 0

    def test_30d_aggregation(self):
        scores = [
            {"sentiment_score": -0.3, "confidence": 0.8, "relevance": 1.0},
            {"sentiment_score": -0.5, "confidence": 0.9, "relevance": 1.0},
            {"sentiment_score": -0.2, "confidence": 0.7, "relevance": 0.8},
            {"sentiment_score": 0.1, "confidence": 0.5, "relevance": 0.5},
        ]
        result = compute_rolling_aggregation(scores, "30D")
        assert result is not None
        assert result.timeframe == "30D"
        assert result.avg_sentiment < 0
        assert result.negative_pct > 0

    def test_press_release_weight(self):
        # Press release should be weighted 0.7x
        scores_normal = [
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": False},
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": False},
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": False},
        ]
        scores_pr = [
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": True},
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": True},
            {"sentiment_score": 0.5, "confidence": 1.0, "relevance": 1.0, "is_press_release": True},
        ]
        r_normal = compute_rolling_aggregation(scores_normal, "7D")
        r_pr = compute_rolling_aggregation(scores_pr, "7D")
        # Both should have same avg since all sentiments are the same,
        # but the weights differ; avg should be identical when all scores match
        assert r_normal is not None
        assert r_pr is not None
        assert r_normal.avg_sentiment == r_pr.avg_sentiment  # same score, different weights

    def test_min_3_articles(self):
        scores = [
            {"sentiment_score": 0.5, "confidence": 0.9, "relevance": 1.0},
            {"sentiment_score": 0.3, "confidence": 0.8, "relevance": 0.7},
        ]
        result = compute_rolling_aggregation(scores, "7D")
        assert result is None

    def test_momentum_classification(self):
        scores = [
            {"sentiment_score": 0.5, "confidence": 0.9, "relevance": 1.0},
            {"sentiment_score": 0.4, "confidence": 0.8, "relevance": 1.0},
            {"sentiment_score": 0.3, "confidence": 0.7, "relevance": 1.0},
        ]
        # Current period avg ~ 0.4, prior period avg = 0.0 -> momentum ~ +0.4 -> STRONGLY_IMPROVING
        result = compute_rolling_aggregation(scores, "7D", prior_avg=0.0)
        assert result is not None
        assert result.momentum is not None
        assert result.momentum > 0
        assert result.momentum_class == "STRONGLY_IMPROVING"


# ═══════════════════════════════════════════════════════════════════════════
# TestPeerZScore
# ═══════════════════════════════════════════════════════════════════════════


class TestPeerZScore:
    def test_normal_z_score(self):
        entity = 0.5
        peers = [0.1, 0.2, 0.15, 0.18, 0.12]
        z = compute_peer_z_score(entity, peers)
        assert z is not None
        assert z > 2.0  # Entity is a clear outlier

    def test_outlier_detection(self):
        entity = -0.8
        peers = [0.1, 0.15, 0.2, 0.05, 0.12]
        z = compute_peer_z_score(entity, peers)
        assert z is not None
        assert abs(z) > 2  # Should be a strong outlier

    def test_too_few_peers(self):
        z = compute_peer_z_score(0.5, [0.1, 0.2])
        assert z is None

    def test_identical_peers(self):
        z = compute_peer_z_score(0.3, [0.3, 0.3, 0.3, 0.3])
        assert z is None  # std = 0


# ═══════════════════════════════════════════════════════════════════════════
# TestDetectAnomalies
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectAnomalies:
    def test_volume_anomaly(self):
        result = detect_anomalies(
            current_volume=40,
            avg_volume=10,
            current_sentiment=0.0,
            historical_sentiments=[0.1, 0.05, -0.05, 0.02, 0.0],
            price_change_pct=0.5,
        )
        assert isinstance(result, CombinedAnomalyResult)
        assert result.volume_anomaly is True
        assert result.combined_score > 0

    def test_sentiment_shift_anomaly(self):
        result = detect_anomalies(
            current_volume=10,
            avg_volume=10,
            current_sentiment=0.8,
            historical_sentiments=[0.0, 0.05, -0.02, 0.01, 0.03],
            price_change_pct=1.0,
        )
        assert result.sentiment_shift_anomaly is True

    def test_price_divergence_positive_sentiment_negative_price(self):
        result = detect_anomalies(
            current_volume=10,
            avg_volume=10,
            current_sentiment=0.5,
            historical_sentiments=[0.4, 0.5, 0.45, 0.55, 0.5],
            price_change_pct=-5.0,
        )
        assert result.price_divergence_anomaly is True

    def test_combined_anomalies(self):
        result = detect_anomalies(
            current_volume=50,
            avg_volume=10,
            current_sentiment=0.8,
            historical_sentiments=[0.0, 0.05, -0.02, 0.01, 0.03],
            price_change_pct=-8.0,
        )
        assert result.volume_anomaly is True
        assert result.sentiment_shift_anomaly is True
        assert result.price_divergence_anomaly is True
        assert result.combined_score > 0
        assert len(result.anomalies) == 3

    def test_no_anomalies(self):
        result = detect_anomalies(
            current_volume=10,
            avg_volume=10,
            current_sentiment=0.05,
            historical_sentiments=[0.1, 0.0, 0.05, -0.02, 0.08],
            price_change_pct=0.5,
        )
        assert result.volume_anomaly is False
        assert result.sentiment_shift_anomaly is False
        assert result.price_divergence_anomaly is False
        assert result.combined_score == 0.0
        assert result.anomalies == []

    def test_edge_zero_avg_volume(self):
        result = detect_anomalies(
            current_volume=5,
            avg_volume=0,
            current_sentiment=0.0,
            historical_sentiments=[0.0, 0.0, 0.0],
            price_change_pct=0.0,
        )
        assert result.volume_anomaly is False


# ═══════════════════════════════════════════════════════════════════════════
# TestKeywordFallback
# ═══════════════════════════════════════════════════════════════════════════


class TestKeywordFallback:
    def test_score_text_uses_keyword(self):
        result = score_text("Strong growth and beat expectations.")
        assert result.method == "KEYWORD"
        assert result.sentiment == "POSITIVE"

    def test_score_paragraphs_works_without_transformers(self):
        results = score_paragraphs(["Good growth.", "Bad loss."])
        assert len(results) == 2
        for r in results:
            assert r.result.method == "KEYWORD"

    def test_entity_specific_works_without_transformers(self):
        text = "Apple had strong growth."
        results = score_entity_specific(text, {"AAPL": ["Apple"]})
        assert len(results) == 1
        assert results[0].entity_id == "AAPL"

    def test_keyword_to_finbert_result_mapping(self):
        result = _keyword_to_finbert_result("Strong growth profits.")
        assert isinstance(result, FinBERTResult)
        assert result.method == "KEYWORD"
        assert result.positive_prob + result.negative_prob + result.neutral_prob == pytest.approx(1.0, abs=0.01)
