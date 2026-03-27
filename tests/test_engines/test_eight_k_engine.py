"""Tests for Pillar 3 Phase 1 — Part 3: 8-K Event Engine."""

import pytest

from src.engines.eight_k_engine import (
    ITEM_DESCRIPTIONS,
    PRIORITY_MAP,
    assess_event_materiality,
    classify_priority,
    extract_key_dates,
    extract_key_people,
    extract_monetary_figures,
    generate_event_summary,
    get_item_description,
    parse_eight_k_items,
)


# ── Priority Classification Tests ────────────────────────────────────────


class TestClassifyPriority:
    """Tests for classify_priority()."""

    def test_classify_priority_immediate_201(self):
        """Item 2.01 (acquisition/disposition) -> priority 1."""
        assert classify_priority("2.01") == 1

    def test_classify_priority_immediate_202(self):
        """Item 2.02 (earnings) -> priority 1."""
        assert classify_priority("2.02") == 1

    def test_classify_priority_immediate_402(self):
        """Item 4.02 (restatement) -> priority 1."""
        assert classify_priority("4.02") == 1

    def test_classify_priority_immediate_502(self):
        """Item 5.02 (CEO/CFO change) -> priority 1."""
        assert classify_priority("5.02") == 1

    def test_classify_priority_same_day_101(self):
        """Item 1.01 (material agreement) -> priority 2."""
        assert classify_priority("1.01") == 2

    def test_classify_priority_same_day_203(self):
        """Item 2.03 (new debt) -> priority 2."""
        assert classify_priority("2.03") == 2

    def test_classify_priority_same_day_501(self):
        """Item 5.01 (change of directors) -> priority 2."""
        assert classify_priority("5.01") == 2

    def test_classify_priority_digest_701(self):
        """Item 7.01 (Reg FD disclosure) -> priority 3."""
        assert classify_priority("7.01") == 3

    def test_classify_priority_digest_801(self):
        """Item 8.01 (other events) -> priority 3."""
        assert classify_priority("8.01") == 3

    def test_classify_priority_digest_901(self):
        """Item 9.01 (financial statements/exhibits) -> priority 3."""
        assert classify_priority("9.01") == 3

    def test_classify_priority_unknown_defaults_to_3(self):
        """Unknown item number defaults to priority 3."""
        assert classify_priority("99.99") == 3
        assert classify_priority("") == 3
        assert classify_priority("6.01") == 3


# ── Item Description Tests ───────────────────────────────────────────────


class TestGetItemDescription:
    """Tests for get_item_description()."""

    def test_get_item_description_known(self):
        assert get_item_description("2.01") == "Completion of Acquisition or Disposition of Assets"
        assert get_item_description("4.02") == "Non-Reliance on Previously Issued Financial Statements"
        assert get_item_description("5.02") == "Departure of Directors or Certain Officers"

    def test_get_item_description_unknown(self):
        assert get_item_description("99.99") == "Unknown Item"


# ── Monetary Extraction Tests ────────────────────────────────────────────


class TestExtractMonetaryFigures:
    """Tests for extract_monetary_figures()."""

    def test_extract_monetary_million(self):
        text = "The company acquired assets valued at $500 million in the transaction."
        results = extract_monetary_figures(text)
        assert len(results) >= 1
        match = results[0]
        assert match["amount_normalized"] == 500_000_000
        assert match["currency"] == "USD"

    def test_extract_monetary_billion(self):
        text = "Total deal consideration was approximately $1.2 billion."
        results = extract_monetary_figures(text)
        assert len(results) >= 1
        assert results[0]["amount_normalized"] == 1_200_000_000

    def test_extract_monetary_plain(self):
        text = "The severance payment totaled $50,000 per the agreement."
        results = extract_monetary_figures(text)
        assert len(results) >= 1
        assert results[0]["amount_normalized"] == 50_000

    def test_extract_monetary_none(self):
        text = "The board held a regular meeting and discussed corporate strategy."
        results = extract_monetary_figures(text)
        assert results == []

    def test_extract_monetary_context_sentence(self):
        text = "Revenue grew. The acquisition cost was $250 million. Further details follow."
        results = extract_monetary_figures(text)
        assert len(results) >= 1
        assert "acquisition" in results[0]["context_sentence"].lower()

    def test_extract_monetary_multiple(self):
        text = "The company paid $100 million for the division and assumed $50 million in debt."
        results = extract_monetary_figures(text)
        assert len(results) == 2


# ── Date Extraction Tests ────────────────────────────────────────────────


class TestExtractKeyDates:
    """Tests for extract_key_dates()."""

    def test_extract_key_dates_month_format(self):
        text = "The agreement was signed on March 15, 2024."
        results = extract_key_dates(text)
        assert len(results) >= 1
        assert results[0]["date_str"] == "March 15, 2024"
        assert results[0]["date_parsed"] == "2024-03-15"
        assert results[0]["label"] == "month_name"

    def test_extract_key_dates_slash_format(self):
        text = "Effective date of the merger is 03/15/2024."
        results = extract_key_dates(text)
        assert len(results) >= 1
        assert results[0]["date_str"] == "03/15/2024"
        assert results[0]["date_parsed"] == "2024-03-15"
        assert results[0]["label"] == "slash"

    def test_extract_key_dates_iso_format(self):
        text = "The filing was submitted on 2024-03-15 to the SEC."
        results = extract_key_dates(text)
        assert len(results) >= 1
        assert results[0]["date_str"] == "2024-03-15"
        assert results[0]["date_parsed"] == "2024-03-15"
        assert results[0]["label"] == "iso"

    def test_extract_key_dates_none(self):
        text = "The company announced a change in its board composition."
        results = extract_key_dates(text)
        assert results == []


# ── People Extraction Tests ──────────────────────────────────────────────


class TestExtractKeyPeople:
    """Tests for extract_key_people()."""

    def test_extract_key_people_appointed(self):
        text = "John Smith has been appointed as Chief Executive Officer."
        results = extract_key_people(text)
        assert len(results) >= 1
        assert results[0]["name"] == "John Smith"
        assert "Chief Executive Officer" in results[0]["role"]
        assert results[0]["action"] == "appointed"

    def test_extract_key_people_resigned(self):
        text = "Jane Doe has resigned as Chief Financial Officer."
        results = extract_key_people(text)
        assert len(results) >= 1
        assert results[0]["name"] == "Jane Doe"
        assert "Chief Financial Officer" in results[0]["role"]
        assert results[0]["action"] == "resigned"

    def test_extract_key_people_terminated(self):
        text = "Robert Brown has been terminated as VP of Operations."
        results = extract_key_people(text)
        assert len(results) >= 1
        assert results[0]["name"] == "Robert Brown"
        assert results[0]["action"] == "terminated"

    def test_extract_key_people_none(self):
        text = "The company entered into a new credit facility agreement."
        results = extract_key_people(text)
        assert results == []


# ── Event Summary Tests ──────────────────────────────────────────────────


class TestGenerateEventSummary:
    """Tests for generate_event_summary()."""

    def test_generate_summary_management_change(self):
        people = [{"name": "John Smith", "role": "Chief Executive Officer", "action": "appointed"}]
        summary = generate_event_summary(
            entity_name="Acme Corp",
            item_number="5.02",
            item_text="John Smith has been appointed as CEO.",
            people=people,
        )
        assert "Acme Corp" in summary
        assert "John Smith" in summary
        assert "management change" in summary.lower()
        assert "IMMEDIATE" in summary

    def test_generate_summary_acquisition(self):
        monetary = [{"amount_raw": "$500 million", "amount_normalized": 500_000_000, "currency": "USD", "context_sentence": "..."}]
        dates = [{"date_str": "March 15, 2024", "date_parsed": "2024-03-15", "label": "month_name", "context": "..."}]
        summary = generate_event_summary(
            entity_name="BigCo Inc.",
            item_number="2.01",
            item_text="Completed acquisition for $500 million on March 15, 2024.",
            monetary=monetary,
            dates=dates,
        )
        assert "BigCo Inc." in summary
        assert "$500 million" in summary
        assert "March 15, 2024" in summary
        assert "IMMEDIATE" in summary

    def test_generate_summary_restatement(self):
        summary = generate_event_summary(
            entity_name="TrustCo",
            item_number="4.02",
            item_text="The company determined certain financial statements should not be relied upon.",
        )
        assert "TrustCo" in summary
        assert "non-reliance" in summary.lower()
        assert "should not be relied upon" in summary.lower()
        assert "IMMEDIATE" in summary

    def test_generate_summary_default_fallback(self):
        summary = generate_event_summary(
            entity_name="GenericCorp",
            item_number="8.01",
            item_text="The company announced a corporate restructuring plan.",
        )
        assert "GenericCorp" in summary
        assert "8-K" in summary
        assert "DAILY DIGEST" in summary


# ── Materiality Assessment Tests ─────────────────────────────────────────


class TestAssessEventMateriality:
    """Tests for assess_event_materiality()."""

    def test_materiality_critical_restatement(self):
        """Item 4.02 (restatement) is always CRITICAL."""
        result = assess_event_materiality("4.02")
        assert result == "CRITICAL"

    def test_materiality_high_priority_1(self):
        """Priority-1 items without large monetary amounts -> HIGH."""
        for item in ("2.01", "2.02", "2.05", "2.06", "5.02"):
            result = assess_event_materiality(item)
            assert result == "HIGH", f"Expected HIGH for item {item}, got {result}"

    def test_materiality_medium_priority_2(self):
        """Priority-2 items without large monetary amounts -> MEDIUM."""
        for item in ("1.01", "1.02", "2.03", "2.04", "3.01", "5.01", "5.07"):
            result = assess_event_materiality(item)
            assert result == "MEDIUM", f"Expected MEDIUM for item {item}, got {result}"

    def test_materiality_low_priority_3(self):
        """Priority-3 items (digest) without monetary amounts -> LOW."""
        for item in ("7.01", "8.01", "9.01"):
            result = assess_event_materiality(item)
            assert result == "LOW", f"Expected LOW for item {item}, got {result}"

    def test_materiality_critical_large_amount(self):
        """Any item with >= $1 billion should be CRITICAL."""
        monetary = [{"amount_raw": "$2.5 billion", "amount_normalized": 2_500_000_000, "currency": "USD", "context_sentence": "..."}]
        result = assess_event_materiality("8.01", monetary=monetary)
        assert result == "CRITICAL"

    def test_materiality_high_from_monetary(self):
        """Any item with >= $100 million should be at least HIGH."""
        monetary = [{"amount_raw": "$250 million", "amount_normalized": 250_000_000, "currency": "USD", "context_sentence": "..."}]
        result = assess_event_materiality("8.01", monetary=monetary)
        assert result == "HIGH"


# ── 8-K Item Parsing Tests ───────────────────────────────────────────────


class TestParseEightKItems:
    """Tests for parse_eight_k_items()."""

    def test_parse_single_item(self):
        html = """<html><body>
        <p><b>Item 5.02</b></p>
        <p>John Smith has resigned as Chief Executive Officer effective immediately.</p>
        </body></html>"""
        items = parse_eight_k_items(html)
        assert len(items) >= 1
        assert items[0]["item_number"] == "5.02"
        assert "resigned" in items[0]["item_text"].lower()

    def test_parse_multiple_items(self):
        html = """<html><body>
        <p><b>Item 2.01</b></p>
        <p>On March 15, 2024 the Company completed the acquisition of WidgetCo for $500 million.</p>
        <p><b>Item 9.01</b></p>
        <p>Financial Statements and Exhibits. The press release is furnished as Exhibit 99.1.</p>
        </body></html>"""
        items = parse_eight_k_items(html)
        assert len(items) >= 2
        numbers = [item["item_number"] for item in items]
        assert "2.01" in numbers
        assert "9.01" in numbers

    def test_parse_empty_html(self):
        items = parse_eight_k_items("")
        assert items == []

    def test_parse_no_items(self):
        html = "<html><body><p>This filing contains no item references.</p></body></html>"
        items = parse_eight_k_items(html)
        assert items == []
