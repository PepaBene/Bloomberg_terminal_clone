"""Sentiment Analysis Engine.

Provides text sentiment scoring, aggregate computation, and earnings call
analysis. Includes keyword-based fallback when AI (LLM) is disabled.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Keyword dictionaries for fallback sentiment scoring
# ---------------------------------------------------------------------------

POSITIVE_WORDS = frozenset({
    "growth", "beat", "exceeded", "strong", "positive", "increase",
    "improved", "profit", "gains", "outperform", "optimistic", "upgrade",
    "momentum", "robust", "accelerating", "record", "upside", "expansion",
    "innovative", "bullish", "recovery", "opportunity", "favorable",
    "surpassed", "strength", "rebound", "confident", "committed",
    "delivered", "exceeded", "outstanding", "remarkable", "transformative",
})

NEGATIVE_WORDS = frozenset({
    "decline", "miss", "weak", "negative", "decrease", "loss",
    "deteriorated", "deficit", "underperform", "pessimistic", "downgrade",
    "headwind", "contraction", "recession", "risk", "concern", "downside",
    "uncertainty", "volatile", "impairment", "restructuring", "challenging",
    "disappointing", "pressure", "slowdown", "warning", "bearish",
    "litigation", "default", "bankruptcy", "layoff", "writedown",
})

HEDGING_WORDS = frozenset({
    "may", "might", "could", "possibly", "uncertain", "contingent",
    "subject to", "depending", "approximate", "estimate", "potential",
    "unclear", "if", "should", "tentative",
})

CONFIDENCE_WORDS = frozenset({
    "will", "committed", "confident", "certain", "guaranteed",
    "definitely", "absolutely", "clearly", "undoubtedly", "firmly",
    "determined", "assured", "demonstrated", "proven", "established",
})


# ---------------------------------------------------------------------------
# Keyword-based sentiment (fallback when AI is disabled)
# ---------------------------------------------------------------------------

@dataclass
class SentimentResult:
    """Result of sentiment analysis on a text."""
    sentiment: str  # POSITIVE, NEUTRAL, NEGATIVE
    score: float  # -1.0 to +1.0
    confidence: float  # 0.0 to 1.0
    positive_count: int = 0
    negative_count: int = 0
    topics: list[str] = field(default_factory=list)


def keyword_sentiment(text: str) -> SentimentResult:
    """Score sentiment using keyword-based heuristic.

    This is the fallback method used when AI/LLM is not available.
    Uses curated positive/negative financial word lists.

    Parameters
    ----------
    text : Input text to analyze.

    Returns
    -------
    SentimentResult with sentiment label, score, and confidence.
    """
    if not text or not text.strip():
        return SentimentResult(
            sentiment="NEUTRAL", score=0.0, confidence=0.0,
        )

    words = re.findall(r'\b[a-z]+\b', text.lower())
    total_words = len(words) or 1

    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)

    # Net score normalized to [-1, 1]
    net = pos_count - neg_count
    denominator = pos_count + neg_count
    if denominator == 0:
        score = 0.0
        confidence = 0.1  # Low confidence when no keywords found
    else:
        score = net / denominator
        # Confidence based on keyword density
        keyword_density = denominator / total_words
        confidence = min(keyword_density * 10, 1.0)  # Scale up
        confidence = max(confidence, 0.2)  # Minimum confidence

    # Classify
    if score > 0.1:
        sentiment = "POSITIVE"
    elif score < -0.1:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return SentimentResult(
        sentiment=sentiment,
        score=round(score, 4),
        confidence=round(confidence, 4),
        positive_count=pos_count,
        negative_count=neg_count,
    )


# ---------------------------------------------------------------------------
# Aggregate sentiment computation
# ---------------------------------------------------------------------------

@dataclass
class AggregateResult:
    """Aggregated sentiment over a time window."""
    avg_sentiment: float
    sentiment_momentum: float | None
    article_count: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    anomaly_flag: bool


def compute_aggregate_sentiment(
    scores: list[dict],
    prior_avg: float | None = None,
) -> AggregateResult:
    """Compute aggregate sentiment from a list of individual scores.

    Parameters
    ----------
    scores : list of dicts with keys: sentiment_score (float), sentiment (str)
    prior_avg : average sentiment from the prior period (for momentum)

    Returns
    -------
    AggregateResult with averages, percentages, momentum, anomaly detection.
    """
    if not scores:
        return AggregateResult(
            avg_sentiment=0.0,
            sentiment_momentum=None,
            article_count=0,
            positive_pct=0.0,
            negative_pct=0.0,
            neutral_pct=0.0,
            anomaly_flag=False,
        )

    n = len(scores)
    values = [s.get("sentiment_score", 0.0) for s in scores]
    avg = sum(values) / n

    # Distribution
    pos_count = sum(1 for s in scores if s.get("sentiment", "").upper() == "POSITIVE")
    neg_count = sum(1 for s in scores if s.get("sentiment", "").upper() == "NEGATIVE")
    neutral_count = n - pos_count - neg_count

    # Momentum vs prior period
    momentum = None
    if prior_avg is not None:
        momentum = round(avg - prior_avg, 4)

    # Anomaly detection: >2 standard deviations from mean
    anomaly = False
    if n >= 3:
        variance = sum((v - avg) ** 2 for v in values) / n
        std = math.sqrt(variance)
        if std > 0 and abs(avg) > 2 * std:
            anomaly = True

    return AggregateResult(
        avg_sentiment=round(avg, 4),
        sentiment_momentum=momentum,
        article_count=n,
        positive_pct=round(pos_count / n, 4),
        negative_pct=round(neg_count / n, 4),
        neutral_pct=round(neutral_count / n, 4),
        anomaly_flag=anomaly,
    )


# ---------------------------------------------------------------------------
# Hedging / Confidence language detection
# ---------------------------------------------------------------------------

def detect_hedging_language(text: str) -> int:
    """Count hedging language instances in text.

    Parameters
    ----------
    text : Input text (typically earnings call transcript).

    Returns
    -------
    Count of hedging phrases/words found.
    """
    if not text:
        return 0
    text_lower = text.lower()
    count = 0
    for word in HEDGING_WORDS:
        count += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
    return count


def detect_confidence_language(text: str) -> int:
    """Count confidence language instances in text.

    Parameters
    ----------
    text : Input text (typically earnings call transcript).

    Returns
    -------
    Count of confidence phrases/words found.
    """
    if not text:
        return 0
    text_lower = text.lower()
    count = 0
    for word in CONFIDENCE_WORDS:
        count += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
    return count


# ---------------------------------------------------------------------------
# Earnings call analysis
# ---------------------------------------------------------------------------

@dataclass
class EarningsCallResult:
    """Result of earnings call sentiment analysis."""
    overall_tone: float
    management_tone: float | None
    qa_tone: float | None
    hedging_count: int
    confidence_count: int
    topic_sentiments: dict[str, float] = field(default_factory=dict)


def analyze_earnings_call(
    transcript: str,
    management_section: str | None = None,
    qa_section: str | None = None,
) -> EarningsCallResult:
    """Analyze earnings call transcript sentiment.

    Uses keyword-based analysis (LLM integration is behind the AI client).

    Parameters
    ----------
    transcript : Full transcript text.
    management_section : Optional management remarks section.
    qa_section : Optional Q&A section.

    Returns
    -------
    EarningsCallResult with tone scores and language analysis.
    """
    # Overall
    overall = keyword_sentiment(transcript)

    # Management section
    mgmt_tone = None
    if management_section:
        mgmt = keyword_sentiment(management_section)
        mgmt_tone = mgmt.score

    # Q&A section
    qa_tone_val = None
    if qa_section:
        qa = keyword_sentiment(qa_section)
        qa_tone_val = qa.score

    # Language analysis on full transcript
    hedging = detect_hedging_language(transcript)
    confidence = detect_confidence_language(transcript)

    return EarningsCallResult(
        overall_tone=overall.score,
        management_tone=mgmt_tone,
        qa_tone=qa_tone_val,
        hedging_count=hedging,
        confidence_count=confidence,
    )
