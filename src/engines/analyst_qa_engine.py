"""Pillar 3 Phase 4B — Analyst Q&A Engine.

Pure computation engine for question parsing, answer assembly,
confidence scoring, and follow-up generation.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import mean


# ── Dataclasses ───────────────────────────────────────────────────────


@dataclass
class QuestionParsed:
    """Parsed question with classification and context."""

    question_type: str  # factual / comparative / forward_looking / scenario / thematic / synthesis
    target_entity: str | None = None
    target_sector: str | None = None
    time_horizon: str | None = None
    context_clues: list[str] = field(default_factory=list)


@dataclass
class DataSource:
    """A data source supporting an answer."""

    source_id: str
    source_type: str  # filing / transcript / research / news / fundamental
    title: str
    date: str
    relevance: str  # high / medium / low
    supporting_claim: str


@dataclass
class FinancialMetric:
    """A financial metric extracted from data."""

    metric: str
    value: float
    unit: str
    date: str
    source: str


@dataclass
class Benchmark:
    """A benchmark comparison for a metric."""

    benchmark: str
    target_value: float
    peer_median: float
    percentile: float
    interpretation: str


@dataclass
class FollowUpSuggestion:
    """A suggested follow-up question."""

    question: str
    relevance_score: float
    reasoning: str


@dataclass
class QAResult:
    """Complete Q&A response."""

    answer_template: str
    confidence: float
    confidence_narrative: str
    answer_type: str
    sources: list[DataSource]
    metrics: list[FinancialMetric]
    benchmarks: list[Benchmark]
    follow_ups: list[FollowUpSuggestion]
    data_completeness: dict


# ── 1. Question Parsing ──────────────────────────────────────────────


def parse_question(question: str) -> QuestionParsed:
    """Parse a natural language question into structured components.

    Extracts entity references ($TICKER or company names), determines
    question type, and identifies context clues.

    Parameters
    ----------
    question : str
        The analyst's question.

    Returns
    -------
    QuestionParsed
    """
    if not question or not question.strip():
        return QuestionParsed(question_type="factual")

    # Extract target entity: $TICKER pattern
    ticker_match = re.search(r"\$([A-Z]{1,5})", question)
    target_entity = ticker_match.group(1) if ticker_match else None

    # If no ticker, try to find company names (simple heuristic: capitalized multi-word)
    if not target_entity:
        # Look for quoted names or well-known patterns
        quoted = re.findall(r'"([^"]+)"', question)
        if quoted:
            target_entity = quoted[0]
        else:
            # Look for "Company X" or "X Inc" / "X Corp" patterns
            corp_match = re.search(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Ltd|Group|Holdings|Co)\b",
                question,
            )
            if corp_match:
                target_entity = corp_match.group(0)

    # Classify question type
    question_type = classify_question_type(question)

    # Extract sector references
    sector_keywords = {
        "tech": "Technology", "technology": "Technology",
        "healthcare": "Health Care", "health care": "Health Care",
        "financial": "Financials", "bank": "Financials",
        "energy": "Energy", "oil": "Energy",
        "consumer": "Consumer",
        "industrial": "Industrials",
        "real estate": "Real Estate",
        "utility": "Utilities", "utilities": "Utilities",
    }
    target_sector = None
    q_lower = question.lower()
    for keyword, sector in sector_keywords.items():
        if keyword in q_lower:
            target_sector = sector
            break

    # Time horizon
    time_horizon = None
    if any(w in q_lower for w in ["next quarter", "q1", "q2", "q3", "q4", "near term", "short term"]):
        time_horizon = "near_term"
    elif any(w in q_lower for w in ["next year", "12 month", "annual", "medium term"]):
        time_horizon = "medium_term"
    elif any(w in q_lower for w in ["long term", "5 year", "decade", "structural"]):
        time_horizon = "long_term"

    # Context clues
    context_clues: list[str] = []
    if "compare" in q_lower or "vs" in q_lower or "versus" in q_lower:
        context_clues.append("comparison_requested")
    if "risk" in q_lower:
        context_clues.append("risk_focus")
    if "valuation" in q_lower or "price target" in q_lower:
        context_clues.append("valuation_focus")
    if "earnings" in q_lower or "revenue" in q_lower:
        context_clues.append("financials_focus")
    if "why" in q_lower or "explain" in q_lower:
        context_clues.append("explanation_requested")
    if "trend" in q_lower or "trajectory" in q_lower:
        context_clues.append("trend_analysis")

    return QuestionParsed(
        question_type=question_type,
        target_entity=target_entity,
        target_sector=target_sector,
        time_horizon=time_horizon,
        context_clues=context_clues,
    )


# ── 2. Question Type Classification ─────────────────────────────────


def classify_question_type(question: str) -> str:
    """Classify question into one of six types using keyword patterns.

    Parameters
    ----------
    question : str

    Returns
    -------
    str
        One of: factual, comparative, forward_looking, scenario,
        thematic, synthesis.
    """
    q_lower = question.lower()

    # Scenario: "what if", "assuming", "if ... then"
    scenario_patterns = ["what if", "assuming", "if ", "scenario", "hypothetical", "suppose"]
    if any(p in q_lower for p in scenario_patterns):
        return "scenario"

    # Forward-looking: future tense, projections
    forward_patterns = [
        "will ", "forecast", "project", "expect", "outlook", "going forward",
        "next quarter", "next year", "future", "predict", "estimate",
    ]
    if any(p in q_lower for p in forward_patterns):
        return "forward_looking"

    # Comparative: "compare", "vs", "versus", "relative to", "better than"
    comparative_patterns = [
        "compare", "vs ", "versus", "relative to", "better than", "worse than",
        "outperform", "underperform", "how does .* stack up",
    ]
    if any(p in q_lower for p in comparative_patterns):
        return "comparative"

    # Thematic: broad themes, sector-wide
    thematic_patterns = [
        "theme", "trend", "sector", "industry", "macro", "structural",
        "secular", "tailwind", "headwind", "disruption",
    ]
    if any(p in q_lower for p in thematic_patterns):
        return "thematic"

    # Synthesis: "summary", "overview", "tell me about", "what do you think"
    synthesis_patterns = [
        "summary", "summarize", "overview", "tell me about",
        "what do you think", "overall", "holistic", "comprehensive",
    ]
    if any(p in q_lower for p in synthesis_patterns):
        return "synthesis"

    # Default: factual
    return "factual"


# ── 3. Required Data Identification ─────────────────────────────────


def identify_required_data(parsed: QuestionParsed) -> list[str]:
    """Determine what data sources are needed to answer the question.

    Parameters
    ----------
    parsed : QuestionParsed

    Returns
    -------
    list[str]
        List of required data source types.
    """
    required: list[str] = []

    # All types need fundamentals if entity is specified
    if parsed.target_entity:
        required.append("fundamentals")

    type_requirements = {
        "factual": ["fundamentals", "filings"],
        "comparative": ["fundamentals", "peer_data", "sector_data"],
        "forward_looking": ["fundamentals", "consensus", "transcripts"],
        "scenario": ["fundamentals", "risk_factors", "macro_data"],
        "thematic": ["sector_data", "macro_data", "research"],
        "synthesis": ["fundamentals", "filings", "transcripts", "research", "news"],
    }

    for source in type_requirements.get(parsed.question_type, ["fundamentals"]):
        if source not in required:
            required.append(source)

    # Add context-specific requirements
    if "risk_focus" in parsed.context_clues:
        if "risk_factors" not in required:
            required.append("risk_factors")
    if "valuation_focus" in parsed.context_clues:
        if "consensus" not in required:
            required.append("consensus")
    if "financials_focus" in parsed.context_clues:
        if "fundamentals" not in required:
            required.append("fundamentals")

    return required


# ── 4. Q&A Prompt Assembly ───────────────────────────────────────────


def assemble_qa_prompt(
    question: str,
    parsed: QuestionParsed,
    data_context: dict,
) -> dict:
    """Build an LLM prompt for answering the analyst's question.

    Parameters
    ----------
    question : str
    parsed : QuestionParsed
    data_context : dict
        Available data organized by type.

    Returns
    -------
    dict
        {system_message, user_message, context_summary}
    """
    system_message = (
        "You are a senior Bloomberg financial analyst assistant. "
        "Answer the question using the provided data context. "
        "Be precise with numbers, cite sources, and note any data gaps. "
        f"Question type: {parsed.question_type}."
    )

    context_parts = []
    for source_type, data in data_context.items():
        if data:
            if isinstance(data, dict):
                context_parts.append(f"[{source_type}]: {data}")
            elif isinstance(data, list):
                context_parts.append(f"[{source_type}]: {len(data)} records available")
            else:
                context_parts.append(f"[{source_type}]: {data}")

    context_summary = "\n".join(context_parts) if context_parts else "No data available"

    entity_info = f"Entity: {parsed.target_entity}" if parsed.target_entity else ""
    sector_info = f"Sector: {parsed.target_sector}" if parsed.target_sector else ""
    horizon_info = f"Time horizon: {parsed.time_horizon}" if parsed.time_horizon else ""

    user_message = (
        f"Question: {question}\n"
        f"{entity_info}\n{sector_info}\n{horizon_info}\n\n"
        f"Available Data:\n{context_summary}"
    ).strip()

    return {
        "system_message": system_message,
        "user_message": user_message,
        "context_summary": context_summary,
    }


# ── 5. Financial Metric Extraction ───────────────────────────────────


def extract_financial_metrics(
    data_context: dict,
    question_type: str,
) -> list[FinancialMetric]:
    """Extract relevant financial metrics from the data context.

    Parameters
    ----------
    data_context : dict
        Data organized by source type. 'fundamentals' key expected.
    question_type : str

    Returns
    -------
    list[FinancialMetric]
    """
    metrics: list[FinancialMetric] = []
    fundamentals = data_context.get("fundamentals", {})

    if not fundamentals:
        return metrics

    # Map of metric name -> (key, unit)
    metric_map = {
        "Revenue": ("revenue", "USD millions"),
        "Revenue Growth": ("revenue_growth", "%"),
        "EPS": ("eps", "USD"),
        "EBITDA": ("ebitda", "USD millions"),
        "EBITDA Margin": ("ebitda_margin", "%"),
        "Operating Margin": ("operating_margin", "%"),
        "Net Income": ("net_income", "USD millions"),
        "ROE": ("roe", "%"),
        "ROIC": ("roic", "%"),
        "FCF": ("fcf", "USD millions"),
        "Debt/Equity": ("debt_equity", "x"),
        "P/E Ratio": ("pe_ratio", "x"),
    }

    # Select metrics based on question type
    if question_type == "comparative":
        priority_metrics = ["Revenue Growth", "EBITDA Margin", "ROE", "P/E Ratio"]
    elif question_type == "forward_looking":
        priority_metrics = ["Revenue Growth", "EPS", "EBITDA", "FCF"]
    elif question_type == "scenario":
        priority_metrics = ["Revenue", "EBITDA", "Debt/Equity", "FCF"]
    else:
        priority_metrics = list(metric_map.keys())[:6]

    date_str = fundamentals.get("date", "2024-12-31")
    source = fundamentals.get("source", "fundamentals")

    for metric_name in priority_metrics:
        if metric_name in metric_map:
            key, unit = metric_map[metric_name]
            value = fundamentals.get(key)
            if value is not None:
                metrics.append(FinancialMetric(
                    metric=metric_name,
                    value=float(value),
                    unit=unit,
                    date=date_str,
                    source=source,
                ))

    return metrics


# ── 6. Benchmark Computation ────────────────────────────────────────


def compute_benchmarks(
    entity_data: dict,
    peer_data: list[dict],
    metrics: list[str],
) -> list[Benchmark]:
    """Compute benchmarks comparing entity metrics to peers.

    Parameters
    ----------
    entity_data : dict
        Entity metrics.
    peer_data : list[dict]
        Peer company metrics.
    metrics : list[str]
        Metric names to benchmark.

    Returns
    -------
    list[Benchmark]
    """
    benchmarks: list[Benchmark] = []

    if not peer_data or not metrics:
        return benchmarks

    for metric in metrics:
        target_value = entity_data.get(metric)
        if target_value is None:
            continue

        peer_values = [p.get(metric) for p in peer_data if p.get(metric) is not None]
        if not peer_values:
            continue

        peer_med = round(sorted(peer_values)[len(peer_values) // 2], 2)
        peer_avg = round(mean(peer_values), 2)

        # Compute percentile
        below_count = sum(1 for v in peer_values if v < target_value)
        percentile = round((below_count / len(peer_values)) * 100, 1)

        # Interpretation
        if percentile >= 75:
            interpretation = f"Top quartile among peers ({percentile:.0f}th percentile)"
        elif percentile >= 50:
            interpretation = f"Above median ({percentile:.0f}th percentile)"
        elif percentile >= 25:
            interpretation = f"Below median ({percentile:.0f}th percentile)"
        else:
            interpretation = f"Bottom quartile ({percentile:.0f}th percentile)"

        benchmarks.append(Benchmark(
            benchmark=metric,
            target_value=float(target_value),
            peer_median=peer_med,
            percentile=percentile,
            interpretation=interpretation,
        ))

    return benchmarks


# ── 7. Confidence Computation ────────────────────────────────────────


def compute_confidence(
    data_completeness: dict,
    answer_type: str,
) -> tuple[float, str]:
    """Compute confidence level and narrative for the answer.

    Parameters
    ----------
    data_completeness : dict
        {source_type: bool} indicating available data.
    answer_type : str
        Type of answer being generated.

    Returns
    -------
    tuple[float, str]
        (confidence_score 0-1, confidence_narrative)
    """
    if not data_completeness:
        return 0.3, "Low confidence — insufficient data available to form a reliable answer."

    total_sources = len(data_completeness)
    available = sum(1 for v in data_completeness.values() if v)

    base_confidence = available / total_sources if total_sources > 0 else 0.3

    # Adjust by answer type complexity
    type_adjustments = {
        "factual": 0.1,
        "comparative": 0.0,
        "forward_looking": -0.1,
        "scenario": -0.15,
        "thematic": -0.05,
        "synthesis": -0.05,
    }
    adjustment = type_adjustments.get(answer_type, 0.0)
    confidence = max(0.1, min(0.99, base_confidence + adjustment))
    confidence = round(confidence, 2)

    # Generate narrative
    if confidence >= 0.8:
        narrative = (
            "High confidence — comprehensive data available across multiple sources. "
            "Answer is well-supported by financial data and qualitative inputs."
        )
    elif confidence >= 0.6:
        narrative = (
            "Moderate confidence — key data sources available but some gaps exist. "
            "Answer captures the main picture but may miss nuances."
        )
    elif confidence >= 0.4:
        narrative = (
            "Limited confidence — several data sources unavailable. "
            "Answer should be validated with additional research."
        )
    else:
        narrative = (
            "Low confidence — insufficient data available to form a reliable answer. "
            "Consider gathering more data before making decisions."
        )

    return confidence, narrative


# ── 8. Follow-Up Generation ──────────────────────────────────────────


def generate_follow_ups(
    question: str,
    parsed: QuestionParsed,
    answer_context: dict,
) -> list[FollowUpSuggestion]:
    """Generate relevant follow-up questions.

    Parameters
    ----------
    question : str
        Original question.
    parsed : QuestionParsed
    answer_context : dict
        Context from the answer: data_gaps, mentioned_entities, etc.

    Returns
    -------
    list[FollowUpSuggestion]
    """
    follow_ups: list[FollowUpSuggestion] = []
    entity = parsed.target_entity or "this company"

    # Type-specific follow-ups
    type_follow_ups = {
        "factual": [
            (f"How does {entity}'s performance compare to peers?", 0.8, "Natural progression to peer comparison"),
            (f"What are the key risks facing {entity}?", 0.7, "Risk assessment complements factual analysis"),
        ],
        "comparative": [
            (f"What drives the valuation gap between {entity} and peers?", 0.85, "Deepens comparison analysis"),
            (f"Which peer has the strongest growth outlook?", 0.7, "Extends competitive analysis"),
        ],
        "forward_looking": [
            (f"What are the key catalysts for {entity} in the next 12 months?", 0.8, "Identifies potential triggers"),
            (f"What could cause {entity} to miss estimates?", 0.75, "Risk to forward outlook"),
        ],
        "scenario": [
            (f"What is the base case valuation for {entity}?", 0.8, "Grounds scenario in fundamentals"),
            (f"How would a recession impact {entity}?", 0.7, "Explores downside scenario"),
        ],
        "thematic": [
            (f"Which companies benefit most from this theme?", 0.8, "Identifies theme beneficiaries"),
            (f"What are the risks to this thematic thesis?", 0.75, "Balances thematic view"),
        ],
        "synthesis": [
            (f"What are the bull and bear cases for {entity}?", 0.85, "Structured thesis framework"),
            (f"How has the investment thesis for {entity} evolved?", 0.7, "Historical context"),
        ],
    }

    base_follow_ups = type_follow_ups.get(parsed.question_type, [])
    for q, score, reason in base_follow_ups:
        follow_ups.append(FollowUpSuggestion(
            question=q,
            relevance_score=score,
            reasoning=reason,
        ))

    # Add data-gap-based follow-ups
    data_gaps = answer_context.get("data_gaps", [])
    for gap in data_gaps[:2]:
        follow_ups.append(FollowUpSuggestion(
            question=f"Can you provide more details on {gap} for {entity}?",
            relevance_score=0.65,
            reasoning=f"Data gap identified: {gap}",
        ))

    # Sort by relevance
    follow_ups.sort(key=lambda x: -x.relevance_score)
    return follow_ups[:5]


# ── 9. Data Completeness Assessment ─────────────────────────────────


def assess_data_completeness(
    required: list[str],
    available: dict,
) -> dict:
    """Assess how complete the available data is relative to requirements.

    Parameters
    ----------
    required : list[str]
        Required data source types.
    available : dict
        Available data keyed by source type.

    Returns
    -------
    dict
        {overall_completeness: float, by_source: dict, missing: list, gaps: list}
    """
    if not required:
        return {
            "overall_completeness": 1.0,
            "by_source": {},
            "missing": [],
            "gaps": [],
        }

    by_source: dict[str, bool] = {}
    missing: list[str] = []

    for source in required:
        has_data = source in available and bool(available[source])
        by_source[source] = has_data
        if not has_data:
            missing.append(source)

    available_count = sum(1 for v in by_source.values() if v)
    overall = round(available_count / len(required), 2) if required else 1.0

    # Identify specific gaps within available data
    gaps: list[str] = []
    for source in missing:
        gaps.append(f"Missing {source} data")

    # Check quality of available data
    fundamentals = available.get("fundamentals", {})
    if isinstance(fundamentals, dict):
        if not fundamentals.get("revenue"):
            gaps.append("Revenue data not available")
        if not fundamentals.get("eps"):
            gaps.append("EPS data not available")

    return {
        "overall_completeness": overall,
        "by_source": by_source,
        "missing": missing,
        "gaps": gaps,
    }


# ── 10. Main Question Processor ─────────────────────────────────────


def process_question(
    question: str,
    entity_data: dict | None,
    peer_data: list[dict] | None,
    research_data: list[dict] | None,
) -> QAResult:
    """Process a question end-to-end and produce a QAResult.

    Parameters
    ----------
    question : str
        The analyst's question.
    entity_data : dict | None
        Entity financial and fundamental data.
    peer_data : list[dict] | None
        Peer company data.
    research_data : list[dict] | None
        Research reports and news.

    Returns
    -------
    QAResult
    """
    # Parse question
    parsed = parse_question(question)

    # Identify required data
    required = identify_required_data(parsed)

    # Build available data context
    available: dict = {}
    if entity_data:
        available["fundamentals"] = entity_data.get("fundamentals", {})
        available["filings"] = entity_data.get("filings", {})
        available["transcripts"] = entity_data.get("transcripts", [])
        available["risk_factors"] = entity_data.get("risk_factors", [])
        available["consensus"] = entity_data.get("consensus", {})
    if peer_data:
        available["peer_data"] = peer_data
        available["sector_data"] = peer_data
    if research_data:
        available["research"] = research_data
        available["news"] = research_data

    # Assess completeness
    completeness = assess_data_completeness(required, available)

    # Extract financial metrics
    metrics = extract_financial_metrics(available, parsed.question_type)

    # Compute benchmarks if peers available
    benchmarks: list[Benchmark] = []
    if peer_data and entity_data:
        benchmark_metrics = [m.metric.lower().replace(" ", "_").replace("/", "_") for m in metrics[:4]]
        entity_metrics = entity_data.get("fundamentals", {})
        benchmarks = compute_benchmarks(entity_metrics, peer_data, benchmark_metrics)

    # Build sources
    sources: list[DataSource] = []
    if entity_data and entity_data.get("fundamentals"):
        sources.append(DataSource(
            source_id="fundamentals",
            source_type="fundamental",
            title="Company Fundamentals",
            date=entity_data.get("fundamentals", {}).get("date", ""),
            relevance="high",
            supporting_claim="Primary financial data",
        ))
    if research_data:
        for rd in research_data[:3]:
            sources.append(DataSource(
                source_id=rd.get("id", ""),
                source_type=rd.get("type", "research"),
                title=rd.get("title", ""),
                date=rd.get("date", ""),
                relevance=rd.get("relevance", "medium"),
                supporting_claim=rd.get("summary", ""),
            ))

    # Compute confidence
    confidence_data = {s: bool(available.get(s)) for s in required}
    confidence, confidence_narrative = compute_confidence(confidence_data, parsed.question_type)

    # Generate follow-ups
    answer_context = {"data_gaps": completeness.get("gaps", [])}
    follow_ups = generate_follow_ups(question, parsed, answer_context)

    # Build answer template
    entity_name = parsed.target_entity or "the target entity"
    metric_summary = ""
    if metrics:
        metric_parts = [f"{m.metric}: {m.value}{m.unit}" for m in metrics[:3]]
        metric_summary = f" Key metrics: {', '.join(metric_parts)}."

    answer_template = (
        f"Based on available data for {entity_name}, "
        f"addressing this {parsed.question_type} question with "
        f"{confidence:.0%} confidence.{metric_summary}"
    )

    return QAResult(
        answer_template=answer_template,
        confidence=confidence,
        confidence_narrative=confidence_narrative,
        answer_type=parsed.question_type,
        sources=sources,
        metrics=metrics,
        benchmarks=benchmarks,
        follow_ups=follow_ups,
        data_completeness=completeness,
    )
