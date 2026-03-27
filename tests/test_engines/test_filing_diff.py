"""Tests for Pillar 3 Phase 1 — Part 2: Filing Diff Engine."""

import pytest

from src.engines.filing_diff import (
    BOILERPLATE_PHRASES,
    SECTION_KEYS,
    FilingDiffResult,
    ParagraphAlignment,
    SectionDiffResult,
    _is_boilerplate_change,
    _is_numerical_only_change,
    align_paragraphs,
    classify_change,
    compute_filing_diff,
    compute_section_diff,
    extract_sections,
    jaccard_similarity,
    split_paragraphs,
    word_overlap_similarity,
)


# ── Section Extraction Tests ──────────────────────────────────────────────


class TestExtractSections:
    """Tests for extract_sections() from 10-K HTML."""

    def test_extract_risk_factors_section(self):
        html = """<html><body>
        <h2>Item 1A. Risk Factors</h2>
        <p>The following are material risks to our business.</p>
        <p>Competition in our industry is intense and we may not be able to maintain our market position.</p>
        <h2>Item 1B. Unresolved Staff Comments</h2>
        <p>None.</p>
        </body></html>"""
        sections = extract_sections(html)
        assert "ITEM_1A" in sections
        assert "material risks" in sections["ITEM_1A"]

    def test_extract_mda_section(self):
        html = """<html><body>
        <h2>Item 7. Management's Discussion and Analysis of Financial Condition</h2>
        <p>Revenue increased 15% year over year driven by strong demand in our cloud segment.</p>
        <p>Operating margins expanded by 200 basis points due to scale efficiencies.</p>
        <h2>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h2>
        <p>We are exposed to market risk from changes in interest rates.</p>
        <h2>Item 8. Financial Statements and Supplementary Data</h2>
        <p>Notes to consolidated financial statements follow.</p>
        </body></html>"""
        sections = extract_sections(html)
        assert "ITEM_7" in sections
        assert "Revenue increased" in sections["ITEM_7"]

    def test_extract_business_description(self):
        html = """<html><body>
        <h2>Item 1. Business</h2>
        <p>We are a leading provider of enterprise software solutions serving Fortune 500 companies.</p>
        <h2>Item 1A. Risk Factors</h2>
        <p>Various risks exist.</p>
        </body></html>"""
        sections = extract_sections(html)
        assert "ITEM_1" in sections
        assert "enterprise software" in sections["ITEM_1"]

    def test_empty_html_returns_empty(self):
        sections = extract_sections("")
        assert sections == {}

    def test_no_matching_sections(self):
        html = "<html><body><p>Just some text with no items.</p></body></html>"
        sections = extract_sections(html)
        assert sections == {}


# ── Paragraph Splitting Tests ─────────────────────────────────────────────


class TestSplitParagraphs:
    """Tests for split_paragraphs()."""

    def test_basic_paragraph_split(self):
        text = (
            "This is the first paragraph about the company's business model "
            "and how it generates revenue from multiple sources.\n\n"
            "This is the second paragraph describing competitive landscape "
            "and market position relative to peers in the industry."
        )
        paras = split_paragraphs(text)
        assert len(paras) == 2
        assert "first paragraph" in paras[0]
        assert "second paragraph" in paras[1]

    def test_filter_short_fragments(self):
        text = "Short.\n\n" + "This is a long enough paragraph that should be kept in the output of the splitting function." * 2
        paras = split_paragraphs(text, min_length=50)
        assert len(paras) == 1  # Short fragment filtered out

    def test_filter_table_data(self):
        text = (
            "123,456 789,012 345,678 901,234\n\n"
            "This is a real paragraph with meaningful text about the company's operations and strategy."
        )
        paras = split_paragraphs(text, min_length=20)
        # Table data (mostly numbers) should be filtered
        assert len(paras) == 1
        assert "real paragraph" in paras[0]

    def test_empty_text_returns_empty(self):
        assert split_paragraphs("") == []
        assert split_paragraphs("   ") == []

    def test_preserves_bullet_points(self):
        text = (
            "Our key risk factors include the following considerations that could materially affect our business:\n\n"
            "• Competition from larger companies with more resources could erode our market share significantly.\n\n"
            "• Regulatory changes in our primary markets could increase compliance costs substantially."
        )
        paras = split_paragraphs(text, min_length=30)
        assert len(paras) >= 1  # At least the main paragraph


# ── Jaccard Similarity Tests ──────────────────────────────────────────────


class TestJaccardSimilarity:
    """Tests for jaccard_similarity()."""

    def test_identical_texts(self):
        text = "the quick brown fox jumps over the lazy dog"
        assert jaccard_similarity(text, text) == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("alpha beta gamma", "delta epsilon zeta") == 0.0

    def test_partial_overlap(self):
        sim = jaccard_similarity(
            "the company reported strong revenue growth",
            "the company announced weak revenue decline",
        )
        assert 0.2 < sim < 0.8  # Partial overlap

    def test_empty_both(self):
        assert jaccard_similarity("", "") == 1.0

    def test_empty_one(self):
        assert jaccard_similarity("some text", "") == 0.0
        assert jaccard_similarity("", "some text") == 0.0

    def test_case_insensitive(self):
        sim = jaccard_similarity("Risk Factors", "risk factors")
        assert sim == 1.0


# ── Word Overlap Similarity Tests ─────────────────────────────────────────


class TestWordOverlapSimilarity:
    """Tests for word_overlap_similarity()."""

    def test_identical(self):
        text = "revenue increased significantly"
        assert word_overlap_similarity(text, text) == 1.0

    def test_subset(self):
        short = "revenue increased"
        long = "revenue increased significantly due to strong market demand"
        sim = word_overlap_similarity(short, long)
        assert sim == 1.0  # All words of shorter text appear in longer

    def test_no_overlap(self):
        assert word_overlap_similarity("alpha beta", "gamma delta") == 0.0

    def test_empty(self):
        assert word_overlap_similarity("", "") == 1.0
        assert word_overlap_similarity("text", "") == 0.0


# ── Paragraph Alignment Tests ─────────────────────────────────────────────


class TestAlignParagraphs:
    """Tests for align_paragraphs()."""

    def test_identical_paragraphs(self):
        old = ["This is a long paragraph about the company's operations and business model."]
        new = ["This is a long paragraph about the company's operations and business model."]
        alignments = align_paragraphs(old, new)
        unchanged = [a for a in alignments if a.type == "UNCHANGED"]
        assert len(unchanged) == 1

    def test_added_paragraph(self):
        old = ["Original paragraph about business operations and growth strategy."]
        new = [
            "Original paragraph about business operations and growth strategy.",
            "A completely new paragraph about emerging cybersecurity risks and data protection requirements.",
        ]
        alignments = align_paragraphs(old, new)
        added = [a for a in alignments if a.type == "ADDED"]
        assert len(added) == 1
        assert "cybersecurity" in added[0].new_text

    def test_removed_paragraph(self):
        old = [
            "First paragraph about revenue growth and market expansion strategies.",
            "Second paragraph about risks from regulatory changes that we no longer face.",
        ]
        new = ["First paragraph about revenue growth and market expansion strategies."]
        alignments = align_paragraphs(old, new)
        removed = [a for a in alignments if a.type == "REMOVED"]
        assert len(removed) == 1
        assert "regulatory changes" in removed[0].old_text

    def test_modified_paragraph(self):
        old = ["The company faces significant competition from large established players in the cloud computing market."]
        new = ["The company faces intense competition from large established players and new AI-focused startups in the cloud computing market."]
        alignments = align_paragraphs(old, new)
        modified = [a for a in alignments if a.type == "MODIFIED"]
        assert len(modified) == 1
        assert modified[0].similarity > 0.5

    def test_empty_old_all_added(self):
        alignments = align_paragraphs(
            [],
            ["New paragraph about emerging risks in the semiconductor supply chain."],
        )
        assert len(alignments) == 1
        assert alignments[0].type == "ADDED"

    def test_empty_new_all_removed(self):
        alignments = align_paragraphs(
            ["Old paragraph about historical competition and market dynamics."],
            [],
        )
        assert len(alignments) == 1
        assert alignments[0].type == "REMOVED"


# ── Change Classification Tests ───────────────────────────────────────────


class TestClassifyChange:
    """Tests for classify_change()."""

    def test_substantive_change(self):
        old = "The company has a strong competitive position in the domestic market."
        new = "The company faces increasing competitive pressure from international rivals entering the domestic market."
        assert classify_change(old, new, "ITEM_1A") == "SUBSTANTIVE"

    def test_boilerplate_change(self):
        old = "This annual report on form 10-k contains forward-looking statements pursuant to the safe harbor provisions of the Private Securities Litigation Reform Act."
        new = "This annual report on form 10-k contains forward-looking statements as defined by the safe harbor provisions of the Private Securities Litigation Reform Act of 1995."
        result = classify_change(old, new, "ITEM_1A")
        assert result == "BOILERPLATE"

    def test_numerical_only_change(self):
        old = "Revenue was $5.2 billion for fiscal year 2023, an increase of 12% from the prior year."
        new = "Revenue was $5.8 billion for fiscal year 2024, an increase of 15% from the prior year."
        assert classify_change(old, new, "ITEM_7") == "NUMERICAL"

    def test_added_paragraph_is_substantive(self):
        assert classify_change(None, "New risk about cybersecurity threats.", "ITEM_1A") == "SUBSTANTIVE"

    def test_removed_paragraph_is_substantive(self):
        assert classify_change("Old risk no longer applicable.", None, "ITEM_1A") == "SUBSTANTIVE"


# ── Section Diff Tests ────────────────────────────────────────────────────


class TestComputeSectionDiff:
    """Tests for compute_section_diff()."""

    def test_identical_sections(self):
        text = (
            "Our company operates in a highly competitive market environment.\n\n"
            "We have experienced consistent revenue growth over the past five fiscal years."
        )
        result = compute_section_diff(text, text, "ITEM_1")
        assert result.change_pct == 0.0
        assert result.classification == "UNCHANGED"
        assert result.materiality == "LOW"

    def test_substantive_changes_in_risk_factors(self):
        old_text = (
            "Competition in our industry is moderate and we maintain a stable market position.\n\n"
            "We have adequate supply chain relationships with diversified suppliers."
        )
        new_text = (
            "Competition in our industry has intensified significantly due to new entrants from China.\n\n"
            "We have experienced critical supply chain disruptions that threaten our ability to fulfill orders.\n\n"
            "A new cybersecurity incident has exposed vulnerabilities in our customer data protection systems."
        )
        result = compute_section_diff(old_text, new_text, "ITEM_1A")
        assert result.substantive_count >= 1
        assert result.materiality in ("HIGH", "CRITICAL")
        assert result.added_count >= 1  # New cybersecurity risk

    def test_change_pct_exceeds_threshold(self):
        old_text = "First paragraph about the business.\n\n" * 3
        new_text = "Completely different text about new strategic direction.\n\n" * 3
        result = compute_section_diff(old_text, new_text, "ITEM_1")
        # Significant changes should result in high change_pct
        assert result.change_pct > 0

    def test_materiality_critical_for_risk_factors(self):
        old_text = "Risk A description is quite long enough to pass the minimum threshold.\n\n" * 2
        new_text = (
            "Entirely new risk X has emerged that significantly threatens our operations.\n\n"
            "Entirely new risk Y about regulatory changes that could impact revenue.\n\n"
            "Entirely new risk Z about technology disruption threatening market position.\n\n"
        )
        result = compute_section_diff(old_text, new_text, "ITEM_1A")
        assert result.materiality in ("HIGH", "CRITICAL")

    def test_empty_sections(self):
        result = compute_section_diff("", "", "ITEM_1")
        assert result.classification == "UNCHANGED"
        assert result.change_pct == 0.0


# ── Filing Diff Tests ─────────────────────────────────────────────────────


class TestComputeFilingDiff:
    """Tests for compute_filing_diff()."""

    def test_identical_filings(self):
        sections = {
            "ITEM_1": "Our business provides enterprise software solutions to Fortune 500 companies worldwide.",
            "ITEM_1A": "We face competition from larger players with more resources in the enterprise software market.",
        }
        result = compute_filing_diff(sections, sections)
        assert result.overall_materiality == "LOW"
        assert result.summary_stats["total_changes"] == 0

    def test_new_section_added(self):
        old = {"ITEM_1": "Business description text about our core operations and market."}
        new = {
            "ITEM_1": "Business description text about our core operations and market.",
            "ITEM_1A": "New risk factors section that was not present in the previous filing version.",
        }
        result = compute_filing_diff(old, new)
        assert "ITEM_1A" in result.new_sections_added
        assert result.overall_materiality == "HIGH"

    def test_section_removed(self):
        old = {
            "ITEM_1": "Business description text.",
            "ITEM_7": "MD&A section with management discussion.",
        }
        new = {"ITEM_1": "Business description text."}
        result = compute_filing_diff(old, new)
        assert "ITEM_7" in result.sections_removed
        assert result.overall_materiality == "HIGH"

    def test_overall_materiality_is_max(self):
        old = {
            "ITEM_1": "Business description that has not changed significantly between filing periods.",
            "ITEM_1A": "Old risk factors that are quite different from new ones and represent material changes.",
        }
        new = {
            "ITEM_1": "Business description that has not changed significantly between filing periods.",
            "ITEM_1A": "Completely rewritten risk factors reflecting entirely new threat landscape and regulatory risks.",
        }
        result = compute_filing_diff(old, new)
        # Overall materiality should be at least as high as the most material section
        assert result.overall_materiality in ("MEDIUM", "HIGH", "CRITICAL")

    def test_empty_filings(self):
        result = compute_filing_diff({}, {})
        assert result.overall_materiality == "LOW"
        assert len(result.section_diffs) == 0

    def test_summary_stats_populated(self):
        old = {"ITEM_1": "Original business description for the company."}
        new = {"ITEM_1": "Updated business description with new market expansion details."}
        result = compute_filing_diff(old, new)
        assert "total_sections_compared" in result.summary_stats
        assert "total_changes" in result.summary_stats


# ── Boilerplate Detection Tests ───────────────────────────────────────────


class TestBoilerplateDetection:
    """Tests for _is_boilerplate_change()."""

    def test_boilerplate_phrase_change(self):
        old = "This report contains forward-looking statements pursuant to the safe harbor provisions."
        new = "This report contains forward-looking statements under the safe harbor provisions of the act."
        assert _is_boilerplate_change(old, new) is True

    def test_substantive_is_not_boilerplate(self):
        old = "We face competition from three major players in our primary market."
        new = "We face competition from seven major players and several new entrants in our primary market."
        assert _is_boilerplate_change(old, new) is False


class TestNumericalOnlyChange:
    """Tests for _is_numerical_only_change()."""

    def test_only_numbers_changed(self):
        old = "Revenue was $5.2 billion for fiscal year 2023."
        new = "Revenue was $5.8 billion for fiscal year 2024."
        assert _is_numerical_only_change(old, new) is True

    def test_text_also_changed(self):
        old = "Revenue increased $5.2 billion for fiscal year 2023."
        new = "Revenue decreased $3.1 billion for fiscal year 2024."
        assert _is_numerical_only_change(old, new) is False


# ── Section Keys Constant Tests ───────────────────────────────────────────


class TestConstants:
    """Verify constants are properly defined."""

    def test_section_keys_defined(self):
        assert "ITEM_1" in SECTION_KEYS
        assert "ITEM_1A" in SECTION_KEYS
        assert "ITEM_7" in SECTION_KEYS
        assert "ITEM_7A" in SECTION_KEYS
        assert "ITEM_8_NOTES" in SECTION_KEYS

    def test_boilerplate_phrases_not_empty(self):
        assert len(BOILERPLATE_PHRASES) >= 20
