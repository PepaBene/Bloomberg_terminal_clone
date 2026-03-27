"""Pillar 3 Phase 2 -- Part 4: FinBERT Sentiment Engine.

Optional FinBERT-based sentiment analysis with keyword fallback.
All functions are pure computation -- no database access.

When the ``transformers`` library is installed, uses FinBERT for
high-quality financial sentiment scoring.  Otherwise, every public
function degrades gracefully to keyword_sentiment() from
sentiment_analysis.py.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from src.engines.sentiment_analysis import keyword_sentiment

# ---------------------------------------------------------------------------
# Optional FinBERT import
# ---------------------------------------------------------------------------

try:
    from transformers import pipeline as _hf_pipeline  # type: ignore[import-untyped]
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _hf_pipeline = None
    _TRANSFORMERS_AVAILABLE = False

# Module-level cache for the lazy-loaded pipeline
_finbert_pipeline: Any = None


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FinBERTResult:
    """Result of FinBERT (or keyword-fallback) sentiment scoring."""
    positive_prob: float
    negative_prob: float
    neutral_prob: float
    composite_score: float  # positive - negative
    confidence: float  # max(probs)
    sentiment: str  # POSITIVE / NEGATIVE / NEUTRAL
    method: str  # FINBERT or KEYWORD


@dataclass
class ParagraphSentimentResult:
    """Per-paragraph sentiment with shift detection."""
    paragraph_index: int
    text_snippet: str  # first 200 chars
    result: FinBERTResult
    sentiment_shift: bool  # differs from prior paragraph


@dataclass
class EntitySentimentResult:
    """Aggregated sentiment for a single entity across sentences."""
    entity_id: str
    sentence_count: int
    avg_sentiment: float
    confidence: float


@dataclass
class RollingAggregation:
    """Rolling sentiment aggregation over a timeframe."""
    timeframe: str  # 7D, 30D, 90D
    avg_sentiment: float
    article_count: int
    positive_pct: float
    negative_pct: float
    momentum: float | None  # 7D vs 30D
    momentum_class: str  # STRONGLY_IMPROVING / IMPROVING / STABLE / DECLINING / STRONGLY_DECLINING


@dataclass
class SentimentAnomaly:
    """A single detected anomaly."""
    anomaly_type: str  # VOLUME, SHIFT, DIVERGENCE
    score: float
    detail: str


@dataclass
class CombinedAnomalyResult:
    """Combined anomaly detection result."""
    anomalies: list
    combined_score: float  # 0-100
    volume_anomaly: bool
    sentiment_shift_anomaly: bool
    price_divergence_anomaly: bool


# ---------------------------------------------------------------------------
# 1. Lazy-load FinBERT pipeline
# ---------------------------------------------------------------------------

def _load_finbert() -> Any | None:
    """Lazy-load the FinBERT pipeline, caching at module level.

    Returns the HuggingFace pipeline or ``None`` when transformers is
    not installed or loading fails.
    """
    global _finbert_pipeline

    if _finbert_pipeline is not None:
        return _finbert_pipeline

    if not _TRANSFORMERS_AVAILABLE:
        return None

    try:
        _finbert_pipeline = _hf_pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            top_k=None,
        )
        return _finbert_pipeline
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2. Score a single text
# ---------------------------------------------------------------------------

def _keyword_to_finbert_result(text: str) -> FinBERTResult:
    """Map keyword_sentiment output to a FinBERTResult."""
    kw = keyword_sentiment(text)

    # Convert keyword score (-1..+1) to probability-like values
    score = kw.score
    if score > 0:
        pos = 0.5 + score * 0.5
        neg = max(0.0, 0.5 - score * 0.5 - 0.15)
        neu = max(0.0, 1.0 - pos - neg)
    elif score < 0:
        neg = 0.5 + abs(score) * 0.5
        pos = max(0.0, 0.5 - abs(score) * 0.5 - 0.15)
        neu = max(0.0, 1.0 - pos - neg)
    else:
        pos = 0.15
        neg = 0.15
        neu = 0.70

    confidence = max(pos, neg, neu)

    sentiment = kw.sentiment  # already POSITIVE / NEGATIVE / NEUTRAL

    return FinBERTResult(
        positive_prob=round(pos, 4),
        negative_prob=round(neg, 4),
        neutral_prob=round(neu, 4),
        composite_score=round(pos - neg, 4),
        confidence=round(confidence, 4),
        sentiment=sentiment,
        method="KEYWORD",
    )


def score_text(text: str) -> FinBERTResult:
    """Score a single text using FinBERT or keyword fallback.

    Parameters
    ----------
    text : str
        Input text to score.

    Returns
    -------
    FinBERTResult with probabilities, composite score, and method used.
    """
    if not text or not text.strip():
        return FinBERTResult(
            positive_prob=0.0,
            negative_prob=0.0,
            neutral_prob=1.0,
            composite_score=0.0,
            confidence=0.0,
            sentiment="NEUTRAL",
            method="KEYWORD",
        )

    pipe = _load_finbert()
    if pipe is not None:
        try:
            # Truncate to model max length
            truncated = text[:512]
            outputs = pipe(truncated)
            # outputs is list of list of dicts: [[{label, score}, ...]]
            results_list = outputs[0] if outputs else []
            probs: dict[str, float] = {}
            for item in results_list:
                label = item["label"].lower()
                probs[label] = item["score"]

            pos = probs.get("positive", 0.0)
            neg = probs.get("negative", 0.0)
            neu = probs.get("neutral", 0.0)
            composite = pos - neg
            confidence = max(pos, neg, neu)

            if pos > neg and pos > neu:
                sentiment = "POSITIVE"
            elif neg > pos and neg > neu:
                sentiment = "NEGATIVE"
            else:
                sentiment = "NEUTRAL"

            return FinBERTResult(
                positive_prob=round(pos, 4),
                negative_prob=round(neg, 4),
                neutral_prob=round(neu, 4),
                composite_score=round(composite, 4),
                confidence=round(confidence, 4),
                sentiment=sentiment,
                method="FINBERT",
            )
        except Exception:
            pass

    # Fallback to keyword
    return _keyword_to_finbert_result(text)


# ---------------------------------------------------------------------------
# 3. Score paragraphs with shift detection
# ---------------------------------------------------------------------------

def score_paragraphs(paragraphs: list[str]) -> list[ParagraphSentimentResult]:
    """Score each paragraph and detect sentiment shifts.

    Parameters
    ----------
    paragraphs : list[str]
        List of paragraph texts.

    Returns
    -------
    list[ParagraphSentimentResult] with shift detection.
    """
    if not paragraphs:
        return []

    results: list[ParagraphSentimentResult] = []
    prev_sentiment: str | None = None

    for i, para in enumerate(paragraphs):
        result = score_text(para)
        shift = prev_sentiment is not None and result.sentiment != prev_sentiment
        results.append(ParagraphSentimentResult(
            paragraph_index=i,
            text_snippet=para[:200],
            result=result,
            sentiment_shift=shift,
        ))
        prev_sentiment = result.sentiment

    return results


# ---------------------------------------------------------------------------
# 4. Entity-specific sentiment
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def score_entity_specific(
    text: str,
    entity_mentions: dict[str, list[str]],
) -> list[EntitySentimentResult]:
    """Score sentiment for sentences mentioning specific entities.

    Parameters
    ----------
    text : str
        Full article text.
    entity_mentions : dict[str, list[str]]
        {entity_id: [mention_string, ...]} for each entity.

    Returns
    -------
    list[EntitySentimentResult] for entities found in the text.
    """
    if not text or not entity_mentions:
        return []

    sentences = _SENTENCE_SPLIT.split(text)
    if not sentences:
        return []

    results: list[EntitySentimentResult] = []

    for entity_id, mentions in entity_mentions.items():
        entity_sentences: list[str] = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(m.lower() in sentence_lower for m in mentions):
                entity_sentences.append(sentence)

        if not entity_sentences:
            continue

        scores: list[float] = []
        confidences: list[float] = []
        for sent in entity_sentences:
            r = score_text(sent)
            scores.append(r.composite_score)
            confidences.append(r.confidence)

        avg_sent = sum(scores) / len(scores) if scores else 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        results.append(EntitySentimentResult(
            entity_id=entity_id,
            sentence_count=len(entity_sentences),
            avg_sentiment=round(avg_sent, 4),
            confidence=round(avg_conf, 4),
        ))

    return results


# ---------------------------------------------------------------------------
# 5. Rolling aggregation
# ---------------------------------------------------------------------------

def _classify_momentum(momentum: float) -> str:
    """Classify momentum into discrete buckets."""
    if momentum > 0.3:
        return "STRONGLY_IMPROVING"
    elif momentum > 0.1:
        return "IMPROVING"
    elif momentum < -0.3:
        return "STRONGLY_DECLINING"
    elif momentum < -0.1:
        return "DECLINING"
    return "STABLE"


def compute_rolling_aggregation(
    scores: list[dict],
    timeframe: str,
    prior_avg: float | None = None,
) -> RollingAggregation | None:
    """Compute weighted rolling sentiment aggregation.

    Parameters
    ----------
    scores : list of dicts with keys:
        sentiment_score (float), confidence (float),
        relevance (float, optional), is_press_release (bool, optional)
    timeframe : str
        Label such as '7D', '30D', '90D'.
    prior_avg : float | None
        Average sentiment from prior period (for momentum).

    Returns
    -------
    RollingAggregation or None if fewer than 3 articles.
    """
    if len(scores) < 3:
        return None

    weighted_scores: list[float] = []
    total_weight = 0.0
    pos_count = 0
    neg_count = 0

    for s in scores:
        sent_score = s.get("sentiment_score", 0.0)
        relevance = s.get("relevance", 1.0)
        confidence = s.get("confidence", 1.0)
        is_pr = s.get("is_press_release", False)

        weight = relevance * confidence
        if is_pr:
            weight *= 0.7

        weighted_scores.append(sent_score * weight)
        total_weight += weight

        if sent_score > 0.1:
            pos_count += 1
        elif sent_score < -0.1:
            neg_count += 1

    avg_sentiment = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0
    n = len(scores)

    momentum: float | None = None
    momentum_class = "STABLE"
    if prior_avg is not None:
        momentum = round(avg_sentiment - prior_avg, 4)
        momentum_class = _classify_momentum(momentum)

    return RollingAggregation(
        timeframe=timeframe,
        avg_sentiment=round(avg_sentiment, 4),
        article_count=n,
        positive_pct=round(pos_count / n, 4),
        negative_pct=round(neg_count / n, 4),
        momentum=momentum,
        momentum_class=momentum_class,
    )


# ---------------------------------------------------------------------------
# 6. Peer Z-score (pure Python, no scipy)
# ---------------------------------------------------------------------------

def compute_peer_z_score(
    entity_sentiment: float,
    peer_sentiments: list[float],
) -> float | None:
    """Compute z-score of entity sentiment vs peers.

    Parameters
    ----------
    entity_sentiment : float
        Sentiment score for the entity of interest.
    peer_sentiments : list[float]
        Sentiment scores for peer entities.

    Returns
    -------
    float z-score or None if insufficient peers (< 3) or zero std.
    """
    if len(peer_sentiments) < 3:
        return None

    n = len(peer_sentiments)
    mean = sum(peer_sentiments) / n
    variance = sum((x - mean) ** 2 for x in peer_sentiments) / n
    std = math.sqrt(variance)

    if std == 0:
        return None

    return round((entity_sentiment - mean) / std, 4)


# ---------------------------------------------------------------------------
# 7. Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    current_volume: int | float,
    avg_volume: int | float,
    current_sentiment: float,
    historical_sentiments: list[float],
    price_change_pct: float,
) -> CombinedAnomalyResult:
    """Detect volume, sentiment shift, and price divergence anomalies.

    Parameters
    ----------
    current_volume : Current article volume.
    avg_volume : Average article volume.
    current_sentiment : Current period sentiment score.
    historical_sentiments : List of prior period sentiment scores.
    price_change_pct : Price change percentage (e.g. -5.0 for -5%).

    Returns
    -------
    CombinedAnomalyResult with individual flags and combined score.
    """
    anomalies: list[SentimentAnomaly] = []
    volume_flag = False
    shift_flag = False
    divergence_flag = False

    # Volume anomaly: > 3x average
    if avg_volume > 0 and current_volume > 3 * avg_volume:
        volume_flag = True
        ratio = current_volume / avg_volume
        anomalies.append(SentimentAnomaly(
            anomaly_type="VOLUME",
            score=min(ratio / 5.0, 1.0),  # Normalize to 0-1
            detail=f"Article volume {current_volume} is {ratio:.1f}x average ({avg_volume})",
        ))

    # Sentiment shift anomaly: |current - mean| > 2 * std
    if len(historical_sentiments) >= 3:
        n = len(historical_sentiments)
        hist_mean = sum(historical_sentiments) / n
        hist_var = sum((x - hist_mean) ** 2 for x in historical_sentiments) / n
        hist_std = math.sqrt(hist_var)

        if hist_std > 0:
            deviation = abs(current_sentiment - hist_mean)
            if deviation > 2 * hist_std:
                shift_flag = True
                z = deviation / hist_std
                anomalies.append(SentimentAnomaly(
                    anomaly_type="SHIFT",
                    score=min(z / 4.0, 1.0),
                    detail=f"Sentiment {current_sentiment:.2f} deviates {z:.1f} sigma from mean {hist_mean:.2f}",
                ))

    # Price divergence: sentiment positive + price drop >3%, or negative + price rise >3%
    if current_sentiment > 0.1 and price_change_pct < -3.0:
        divergence_flag = True
        anomalies.append(SentimentAnomaly(
            anomaly_type="DIVERGENCE",
            score=min(abs(price_change_pct) / 10.0, 1.0),
            detail=f"Positive sentiment ({current_sentiment:.2f}) but price dropped {price_change_pct:.1f}%",
        ))
    elif current_sentiment < -0.1 and price_change_pct > 3.0:
        divergence_flag = True
        anomalies.append(SentimentAnomaly(
            anomaly_type="DIVERGENCE",
            score=min(price_change_pct / 10.0, 1.0),
            detail=f"Negative sentiment ({current_sentiment:.2f}) but price rose {price_change_pct:.1f}%",
        ))

    # Combined score: weighted sum, 0-100
    if anomalies:
        # Weights: VOLUME=30, SHIFT=40, DIVERGENCE=30
        weight_map = {"VOLUME": 30.0, "SHIFT": 40.0, "DIVERGENCE": 30.0}
        weighted_sum = 0.0
        for a in anomalies:
            w = weight_map.get(a.anomaly_type, 30.0)
            weighted_sum += a.score * w
        combined = min(weighted_sum, 100.0)
    else:
        combined = 0.0

    return CombinedAnomalyResult(
        anomalies=anomalies,
        combined_score=round(combined, 2),
        volume_anomaly=volume_flag,
        sentiment_shift_anomaly=shift_flag,
        price_divergence_anomaly=divergence_flag,
    )
