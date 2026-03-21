"""Tests for the sentiment analysis engine (Pillar 2 Supplement – Part 8)."""

import pytest

from src.engines.sentiment_analysis import (
    SentimentResult,
    AggregateResult,
    EarningsCallResult,
    keyword_sentiment,
    compute_aggregate_sentiment,
    detect_hedging_language,
    detect_confidence_language,
    analyze_earnings_call,
)


class TestKeywordSentiment:
    def test_positive_text(self):
        text = "The company reported strong growth and beat expectations with record profits."
        result = keyword_sentiment(text)
        assert result.sentiment == "POSITIVE"
        assert result.score > 0
        assert result.positive_count > 0

    def test_negative_text(self):
        text = "Revenue decline and earnings miss led to a significant loss and downgrade."
        result = keyword_sentiment(text)
        assert result.sentiment == "NEGATIVE"
        assert result.score < 0
        assert result.negative_count > 0

    def test_neutral_text(self):
        text = "The company held its annual meeting on Tuesday in New York."
        result = keyword_sentiment(text)
        assert result.sentiment == "NEUTRAL"
        assert abs(result.score) <= 0.1

    def test_empty_text(self):
        result = keyword_sentiment("")
        assert result.sentiment == "NEUTRAL"
        assert result.score == 0.0
        assert result.confidence == 0.0

    def test_none_text(self):
        result = keyword_sentiment(None)
        assert result.sentiment == "NEUTRAL"

    def test_mixed_text(self):
        text = "Despite strong revenue growth, the company faced a decline in margins."
        result = keyword_sentiment(text)
        assert isinstance(result, SentimentResult)
        # Mixed signals should have both positive and negative counts
        assert result.positive_count > 0
        assert result.negative_count > 0

    def test_confidence_increases_with_keywords(self):
        few_keywords = "The company showed growth."
        many_keywords = "Strong growth, beat expectations, record profits, positive gains, outperform."
        r1 = keyword_sentiment(few_keywords)
        r2 = keyword_sentiment(many_keywords)
        assert r2.confidence >= r1.confidence

    def test_returns_sentiment_result(self):
        result = keyword_sentiment("test text")
        assert isinstance(result, SentimentResult)
        assert result.sentiment in ("POSITIVE", "NEUTRAL", "NEGATIVE")
        assert -1.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0


class TestComputeAggregateSentiment:
    def test_positive_aggregate(self):
        scores = [
            {"sentiment_score": 0.5, "sentiment": "POSITIVE"},
            {"sentiment_score": 0.3, "sentiment": "POSITIVE"},
            {"sentiment_score": 0.1, "sentiment": "NEUTRAL"},
        ]
        result = compute_aggregate_sentiment(scores)
        assert result.avg_sentiment > 0
        assert result.article_count == 3
        assert result.positive_pct == pytest.approx(2 / 3, abs=0.01)

    def test_negative_aggregate(self):
        scores = [
            {"sentiment_score": -0.5, "sentiment": "NEGATIVE"},
            {"sentiment_score": -0.3, "sentiment": "NEGATIVE"},
        ]
        result = compute_aggregate_sentiment(scores)
        assert result.avg_sentiment < 0
        assert result.negative_pct == 1.0

    def test_empty_scores(self):
        result = compute_aggregate_sentiment([])
        assert result.avg_sentiment == 0.0
        assert result.article_count == 0
        assert result.anomaly_flag is False

    def test_momentum_calculation(self):
        scores = [
            {"sentiment_score": 0.5, "sentiment": "POSITIVE"},
        ]
        result = compute_aggregate_sentiment(scores, prior_avg=0.2)
        assert result.sentiment_momentum is not None
        assert result.sentiment_momentum == pytest.approx(0.3, abs=0.01)

    def test_momentum_none_when_no_prior(self):
        scores = [{"sentiment_score": 0.5, "sentiment": "POSITIVE"}]
        result = compute_aggregate_sentiment(scores)
        assert result.sentiment_momentum is None

    def test_distribution_sums_to_one(self):
        scores = [
            {"sentiment_score": 0.5, "sentiment": "POSITIVE"},
            {"sentiment_score": -0.3, "sentiment": "NEGATIVE"},
            {"sentiment_score": 0.0, "sentiment": "NEUTRAL"},
        ]
        result = compute_aggregate_sentiment(scores)
        total = result.positive_pct + result.negative_pct + result.neutral_pct
        assert total == pytest.approx(1.0, abs=0.01)


class TestDetectHedgingLanguage:
    def test_hedging_detected(self):
        text = "We may see some improvement, but this could possibly change depending on conditions."
        count = detect_hedging_language(text)
        assert count >= 3  # may, could, possibly, depending

    def test_no_hedging(self):
        text = "The company reported strong results this quarter."
        count = detect_hedging_language(text)
        assert count == 0

    def test_empty_text(self):
        assert detect_hedging_language("") == 0
        assert detect_hedging_language(None) == 0


class TestDetectConfidenceLanguage:
    def test_confidence_detected(self):
        text = "We are committed to growth and will definitely deliver strong results. We are confident."
        count = detect_confidence_language(text)
        assert count >= 3  # committed, will, definitely, confident

    def test_no_confidence(self):
        text = "The company had a meeting."
        count = detect_confidence_language(text)
        assert count == 0

    def test_empty_text(self):
        assert detect_confidence_language("") == 0
        assert detect_confidence_language(None) == 0


class TestAnalyzeEarningsCall:
    def test_basic_analysis(self):
        transcript = "We delivered strong growth and beat expectations. Revenue increased significantly."
        result = analyze_earnings_call(transcript)
        assert isinstance(result, EarningsCallResult)
        assert result.overall_tone > 0

    def test_with_sections(self):
        mgmt = "We are confident and committed to delivering strong growth."
        qa = "There is uncertainty and risk around the outlook. We may face headwinds."
        full = mgmt + " " + qa
        result = analyze_earnings_call(full, management_section=mgmt, qa_section=qa)
        assert result.management_tone is not None
        assert result.qa_tone is not None
        assert result.management_tone > result.qa_tone  # Mgmt more positive

    def test_hedging_and_confidence_counts(self):
        transcript = "We will definitely deliver. But we may face uncertain conditions."
        result = analyze_earnings_call(transcript)
        assert result.hedging_count > 0
        assert result.confidence_count > 0

    def test_empty_transcript(self):
        result = analyze_earnings_call("")
        assert result.overall_tone == 0.0
        assert result.hedging_count == 0
        assert result.confidence_count == 0

    def test_no_sections_returns_none_tones(self):
        result = analyze_earnings_call("some text")
        assert result.management_tone is None
        assert result.qa_tone is None
