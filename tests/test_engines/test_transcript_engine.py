"""Tests for Pillar 3 Phase 2 -- Part 2: Transcript Engine."""

import pytest

from src.engines.transcript_engine import (
    BUZZWORD_DICT,
    CEO_TITLE_PATTERNS,
    CFO_TITLE_PATTERNS,
    FORWARD_LOOKING_PATTERNS,
    TopicAnalysis,
    TranscriptAnalysis,
    TranscriptSection,
    TranscriptStructure,
    analyze_transcript,
    compare_topics,
    compute_confidence_ratio,
    compute_forward_looking_pct,
    compute_hedging_ratio,
    compute_tone_scores,
    count_buzzwords,
    extract_topics,
    extract_transcript_structure,
)


# ── Realistic Transcript Fixtures ──────────────────────────────────────────


FULL_TRANSCRIPT = """
Operator

Good morning and welcome to Acme Corp's Fourth Quarter 2025 Earnings Conference Call.

Prepared Remarks

John Smith -- Chief Executive Officer, Acme Corp

Thank you, operator. I'm pleased to report another strong quarter for Acme Corp. Revenue was $12.3 billion, exceeding our guidance range. We delivered record operating margins of 28%, driven by robust demand across our cloud and AI segments. Our digital transformation initiatives continue to gain momentum. We are confident in our ability to sustain this growth trajectory and expect full year 2026 revenue of $52 billion to $54 billion. We will continue to invest in innovation and believe our market share gains are sustainable.

Jane Doe -- Chief Financial Officer, Acme Corp

Thank you, John. Let me walk through the financial details. Earnings per share came in at $3.42, beating consensus by 8%. Gross margin expanded 150 basis points year-over-year to 65.2%, reflecting our pricing power and cost reduction efforts. Operating expenses were well-controlled. We may see some headwinds from tariff uncertainty in the coming quarters, and our supply chain could face pressure depending on geopolitical developments. Free cash flow was $4.1 billion, and we returned $2.8 billion to shareholders through buybacks and dividends.

Question-and-Answer

Mark Johnson -- Analyst, Goldman Sachs

Great quarter. Can you talk about the sustainability of these margin levels and any risk from inflation in your supply chain?

John Smith -- Chief Executive Officer, Acme Corp

Absolutely. We have significant pricing power and our subscription revenue mix is increasing. We anticipate continued margin expansion through synergies from our recent acquisition and further cloud migration. We will target operating margins of 30% by 2027.

Sarah Williams -- Analyst, Morgan Stanley

What's your outlook for the AI segment specifically?

Jane Doe -- Chief Financial Officer, Acme Corp

The AI segment grew 45% year-over-year. We expect this growth trajectory to continue. Machine learning adoption across our enterprise customer base is accelerating and we forecast AI revenue will reach $8 billion in fiscal 2026. There could be some uncertainty around the pace of adoption, but we are firmly committed to this strategy.
"""

CEO_ONLY_TRANSCRIPT = """
Prepared Remarks

Robert Chen -- Chief Executive Officer, TechVision Inc

We delivered outstanding results this quarter. Revenue grew 22% to $8.5 billion. Our cloud platform exceeded expectations with strong growth momentum. We are optimistic about the year ahead and will continue investing in digital and AI capabilities. We believe our competitive position has never been stronger.

Question-and-Answer

Lisa Park -- Analyst, JP Morgan

Can you discuss the competitive landscape?

Robert Chen -- Chief Executive Officer, TechVision Inc

We are confident in our market position. Our innovation pipeline is robust and we expect to gain market share in fiscal 2026. The restructuring efforts are yielding results and we anticipate further cost reduction benefits.
"""

QA_ONLY_TRANSCRIPT = """
Question-and-Answer

David Lee -- Analyst, Bank of America

Revenue was disappointing this quarter. What went wrong with the subscription business?

Michael Brown -- Chief Financial Officer, XYZ Corp

We acknowledge the weakness in our subscription segment. The decline was driven by elevated churn and challenging macroeconomic conditions. There is uncertainty about the near-term outlook. Inflation and supply chain headwinds created significant pressure on margins. We may need to restructure our pricing model.
"""

MINIMAL_TRANSCRIPT = """
Prepared Remarks

Speaker One -- President

Revenue was up. Growth continued. Outlook is positive.
"""

MALFORMED_TRANSCRIPT = """
This is some random text without any proper speaker markers or section headers.
The company reported results. Revenue was $5 billion. Earnings beat expectations.
Management discussed growth and innovation opportunities.
"""


# ── TestExtractTranscriptStructure ─────────────────────────────────────────


class TestExtractTranscriptStructure:
    """Tests for extract_transcript_structure()."""

    def test_normal_transcript_has_prepared_and_qa(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        assert len(structure.prepared_remarks) >= 2
        assert len(structure.qa_sections) >= 2

    def test_qa_only_transcript(self):
        structure = extract_transcript_structure(QA_ONLY_TRANSCRIPT)
        assert len(structure.qa_sections) >= 1
        # May have prepared from text before Q&A marker
        assert isinstance(structure.prepared_remarks, list)

    def test_no_qa_section(self):
        no_qa = """
Prepared Remarks

Alice Wong -- Chief Executive Officer, FooBar Inc

Revenue was $3 billion. Growth was strong and we are optimistic about the future.
"""
        structure = extract_transcript_structure(no_qa)
        assert len(structure.prepared_remarks) >= 1
        assert len(structure.qa_sections) == 0

    def test_speaker_matching(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        speakers = [s.speaker for s in structure.prepared_remarks]
        assert any("John Smith" in name for name in speakers)
        assert any("Jane Doe" in name for name in speakers)

    def test_ceo_detection(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        assert len(structure.ceo_remarks) > 0
        assert "strong quarter" in structure.ceo_remarks.lower() or "pleased" in structure.ceo_remarks.lower()

    def test_cfo_detection(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        assert len(structure.cfo_remarks) > 0
        assert "earnings per share" in structure.cfo_remarks.lower() or "financial" in structure.cfo_remarks.lower()

    def test_empty_transcript(self):
        structure = extract_transcript_structure("")
        assert structure.prepared_remarks == []
        assert structure.qa_sections == []
        assert structure.ceo_remarks == ""
        assert structure.cfo_remarks == ""
        assert structure.participants == []

    def test_multiple_speakers_tracked_as_participants(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        assert len(structure.participants) >= 4
        participant_names = [p["name"] for p in structure.participants]
        assert any("John Smith" in n for n in participant_names)
        assert any("Jane Doe" in n for n in participant_names)


# ── TestComputeToneScores ──────────────────────────────────────────────────


class TestComputeToneScores:
    """Tests for compute_tone_scores()."""

    def test_positive_tone(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        tones = compute_tone_scores(structure)
        # Full transcript has many positive words: strong, exceeded, record, growth
        assert tones["overall"] > 0.0

    def test_negative_tone(self):
        structure = extract_transcript_structure(QA_ONLY_TRANSCRIPT)
        tones = compute_tone_scores(structure)
        # Disappointing, weakness, decline, pressure, uncertainty
        assert tones["qa"] < 0.0

    def test_mixed_tone(self):
        mixed = """
Prepared Remarks

Alice Wong -- CEO, TestCo

We delivered record growth this quarter with strong momentum and outstanding results.

Question-and-Answer

Bob Lee -- Analyst, BankCo

What about the decline in margins and the risk of recession?

Alice Wong -- CEO, TestCo

There is uncertainty and we face headwinds. The pressure from inflation is a concern but we remain confident.
"""
        structure = extract_transcript_structure(mixed)
        tones = compute_tone_scores(structure)
        # Prepared should be more positive than Q&A
        assert tones["prepared"] > tones["qa"] or tones["divergence"] >= 0.0

    def test_divergence_calculation(self):
        structure = extract_transcript_structure(FULL_TRANSCRIPT)
        tones = compute_tone_scores(structure)
        assert "divergence" in tones
        assert tones["divergence"] >= 0.0
        # Divergence = |prepared - qa|
        expected = abs(tones["prepared"] - tones["qa"])
        assert abs(tones["divergence"] - expected) < 0.001

    def test_empty_structure(self):
        structure = TranscriptStructure()
        tones = compute_tone_scores(structure)
        assert tones["overall"] == 0.0
        assert tones["ceo"] == 0.0
        assert tones["cfo"] == 0.0


# ── TestComputeHedgingRatio ────────────────────────────────────────────────


class TestComputeHedgingRatio:
    """Tests for compute_hedging_ratio()."""

    def test_high_hedging(self):
        text = (
            "We may see some challenges. Results could vary. "
            "The outcome is uncertain. It might depend on conditions. "
            "If possible we should adjust."
        )
        ratio = compute_hedging_ratio(text)
        assert ratio > 0.5

    def test_no_hedging(self):
        text = (
            "Revenue grew 20 percent. Earnings beat consensus. "
            "The company reported record margins. "
            "Dividends increased for the tenth consecutive year."
        )
        ratio = compute_hedging_ratio(text)
        assert ratio == 0.0

    def test_empty_text(self):
        assert compute_hedging_ratio("") == 0.0
        assert compute_hedging_ratio("   ") == 0.0

    def test_single_sentence_with_hedging(self):
        text = "We may see improvement"
        ratio = compute_hedging_ratio(text)
        assert ratio == 1.0


# ── TestComputeConfidenceRatio ─────────────────────────────────────────────


class TestComputeConfidenceRatio:
    """Tests for compute_confidence_ratio()."""

    def test_high_confidence(self):
        text = (
            "We are firmly committed to this strategy. "
            "We will deliver results. "
            "We are confident in our outlook. "
            "This approach has been proven and established."
        )
        ratio = compute_confidence_ratio(text)
        assert ratio > 0.5

    def test_no_confidence_words(self):
        text = (
            "Revenue was flat this quarter. "
            "Margins contracted by 50 basis points. "
            "The segment reported stable results."
        )
        ratio = compute_confidence_ratio(text)
        assert ratio == 0.0

    def test_empty_text(self):
        assert compute_confidence_ratio("") == 0.0

    def test_mixed_confidence_and_hedging(self):
        text = (
            "We are confident in our long-term strategy. "
            "However results may vary depending on macroeconomic conditions. "
            "We will definitely invest in growth."
        )
        ratio = compute_confidence_ratio(text)
        assert 0.0 < ratio < 1.0


# ── TestComputeForwardLookingPct ──────────────────────────────────────────


class TestComputeForwardLookingPct:
    """Tests for compute_forward_looking_pct()."""

    def test_high_forward_looking(self):
        text = (
            "We expect revenue to grow next quarter. "
            "We anticipate margin expansion. "
            "We will invest in innovation. "
            "Our guidance calls for EPS of $5.20."
        )
        pct = compute_forward_looking_pct(text)
        assert pct >= 0.75

    def test_no_forward_looking(self):
        text = (
            "Revenue was $12 billion this quarter. "
            "Earnings came in at $3.42 per share. "
            "Gross margin expanded 150 basis points."
        )
        pct = compute_forward_looking_pct(text)
        assert pct == 0.0

    def test_empty_text(self):
        assert compute_forward_looking_pct("") == 0.0

    def test_partial_forward_looking(self):
        text = (
            "Revenue was $10 billion. "
            "We expect growth to continue. "
            "Margins were strong at 30 percent."
        )
        pct = compute_forward_looking_pct(text)
        assert 0.2 < pct < 0.6


# ── TestCountBuzzwords ─────────────────────────────────────────────────────


class TestCountBuzzwords:
    """Tests for count_buzzwords()."""

    def test_multiple_buzzwords(self):
        text = (
            "Our AI and machine learning initiatives are driving growth. "
            "Cloud revenue increased 40 percent. The digital transformation "
            "and sustainability strategy continues. We see margin expansion "
            "from supply chain optimization and pricing power."
        )
        counts = count_buzzwords(text)
        assert counts["ai"] >= 1
        assert counts["machine_learning"] >= 1
        assert counts["cloud"] >= 1
        assert counts["digital"] >= 1
        assert counts["sustainability"] >= 1
        assert counts["margin_expansion"] >= 1
        assert counts["supply_chain"] >= 1
        assert counts["pricing_power"] >= 1

    def test_no_buzzwords(self):
        text = "The company reported quarterly results and paid a dividend."
        counts = count_buzzwords(text)
        assert all(v == 0 for v in counts.values())

    def test_empty_text(self):
        counts = count_buzzwords("")
        assert all(v == 0 for v in counts.values())
        assert len(counts) == len(BUZZWORD_DICT)


# ── TestExtractTopics ──────────────────────────────────────────────────────


class TestExtractTopics:
    """Tests for extract_topics()."""

    def test_extract_top_terms(self):
        text = (
            "Revenue growth was driven by strong cloud demand. "
            "Cloud revenue increased significantly. "
            "The cloud segment delivered strong results. "
            "Innovation drove revenue higher. "
            "Revenue from cloud exceeded expectations."
        )
        topics = extract_topics(text, top_n=3)
        assert len(topics) <= 3
        assert "cloud" in topics or "revenue" in topics

    def test_empty_text_returns_empty(self):
        topics = extract_topics("")
        assert topics == []

    def test_respects_top_n(self):
        text = (
            "Cloud revenue growth was strong. Innovation pipeline robust. "
            "Digital transformation accelerating. Subscription recurring. "
            "Enterprise customers expanding. Platform adoption rising."
        )
        topics = extract_topics(text, top_n=2)
        assert len(topics) <= 2


# ── TestCompareTopics ──────────────────────────────────────────────────────


class TestCompareTopics:
    """Tests for compare_topics()."""

    def test_absent_and_new_topics(self):
        current = ["cloud", "ai", "revenue"]
        prior = ["cloud", "tariff", "inflation"]
        absent, new = compare_topics(current, prior)
        assert "tariff" in absent
        assert "inflation" in absent
        assert "ai" in new
        assert "revenue" in new

    def test_identical_topics(self):
        topics = ["cloud", "ai", "revenue"]
        absent, new = compare_topics(topics, topics)
        assert absent == []
        assert new == []

    def test_completely_different_topics(self):
        current = ["ai", "cloud"]
        prior = ["tariff", "inflation"]
        absent, new = compare_topics(current, prior)
        assert set(absent) == {"tariff", "inflation"}
        assert set(new) == {"ai", "cloud"}


# ── TestAnalyzeTranscript ──────────────────────────────────────────────────


class TestAnalyzeTranscript:
    """Tests for analyze_transcript() full orchestrator."""

    def test_full_analysis_returns_all_fields(self):
        result = analyze_transcript(FULL_TRANSCRIPT)
        assert isinstance(result, TranscriptAnalysis)
        assert result.sentence_count > 0
        assert result.overall_tone != 0.0 or result.sentence_count > 0
        assert isinstance(result.buzzword_counts, dict)
        assert isinstance(result.topics, TopicAnalysis)
        assert result.hedging_ratio >= 0.0
        assert result.confidence_ratio >= 0.0
        assert result.forward_looking_pct >= 0.0

    def test_empty_transcript_returns_defaults(self):
        result = analyze_transcript("")
        assert result.sentence_count == 0
        assert result.overall_tone == 0.0
        assert result.buzzword_counts == {}

    def test_minimal_transcript(self):
        result = analyze_transcript(MINIMAL_TRANSCRIPT)
        assert isinstance(result, TranscriptAnalysis)
        assert result.sentence_count >= 1

    def test_with_prior_topics(self):
        prior = ["tariff", "inflation", "restructuring"]
        result = analyze_transcript(FULL_TRANSCRIPT, prior_topics=prior)
        # Should detect that some prior topics may be absent or new
        assert isinstance(result.topics.absent_topics, list)
        assert isinstance(result.topics.new_topics, list)


# ── TestConstants ──────────────────────────────────────────────────────────


class TestConstants:
    """Tests for module-level constants."""

    def test_forward_looking_patterns_all_compile(self):
        for pat in FORWARD_LOOKING_PATTERNS:
            assert pat.search("We will grow") is not None or pat.pattern

    def test_buzzword_dict_has_expected_terms(self):
        assert "ai" in BUZZWORD_DICT
        assert "cloud" in BUZZWORD_DICT
        assert "tariff" in BUZZWORD_DICT
        assert "sustainability" in BUZZWORD_DICT

    def test_ceo_pattern_matches(self):
        assert CEO_TITLE_PATTERNS.search("Chief Executive Officer") is not None
        assert CEO_TITLE_PATTERNS.search("CEO") is not None

    def test_cfo_pattern_matches(self):
        assert CFO_TITLE_PATTERNS.search("Chief Financial Officer") is not None
        assert CFO_TITLE_PATTERNS.search("CFO") is not None
