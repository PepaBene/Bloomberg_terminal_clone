"""Tests for Pillar 4 Phase 1 — CSV/Excel Upload Parsing Engine."""

import pytest

from src.engines.csv_upload_engine import (
    build_position_list,
    compute_upload_summary,
    detect_duplicates,
    generate_upload_error_report,
    normalize_tickers,
    parse_csv_holdings,
    parse_date_flexible,
    suggest_close_matches,
    validate_numeric_fields,
    validate_required_fields,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _standard_csv() -> str:
    """Standard 5-row CSV."""
    return (
        "ticker,shares,cost_basis,acquisition_date\n"
        "AAPL,100,150.00,2024-01-15\n"
        "MSFT,80,300.00,2024-02-20\n"
        "JNJ,120,160.00,2024-03-10\n"
        "JPM,90,140.00,2024-04-05\n"
        "PG,110,130.00,2024-05-12\n"
    )


# ── TestParseCSV ──────────────────────────────────────────────────────


class TestParseCSV:
    """Tests for parse_csv_holdings."""

    def test_standard_five_rows(self):
        """Parse standard 5-row CSV."""
        rows = parse_csv_holdings(_standard_csv())
        assert len(rows) == 5
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["shares"] == "100"

    def test_tab_delimited(self):
        """Parse tab-delimited file."""
        content = "ticker\tshares\tcost_basis\nAAPL\t100\t150\nMSFT\t80\t300\n"
        rows = parse_csv_holdings(content, delimiter="\t")
        assert len(rows) == 2
        assert rows[0]["ticker"] == "AAPL"

    def test_empty_file(self):
        """Empty file returns empty list."""
        rows = parse_csv_holdings("")
        assert rows == []

    def test_malformed_content(self):
        """Header only, no data rows."""
        rows = parse_csv_holdings("ticker,shares,cost_basis\n")
        assert rows == []


# ── TestValidateFields ────────────────────────────────────────────────


class TestValidateFields:
    """Tests for validate_required_fields."""

    def test_all_valid(self):
        """All rows have required fields."""
        rows = parse_csv_holdings(_standard_csv())
        valid, errors = validate_required_fields(rows)
        assert len(valid) == 5
        assert len(errors) == 0

    def test_missing_ticker(self):
        """Missing ticker triggers error."""
        rows = [{"ticker": "", "shares": "100"}]
        valid, errors = validate_required_fields(rows)
        assert len(valid) == 0
        assert len(errors) == 1
        assert errors[0]["field"] == "ticker"

    def test_missing_shares(self):
        """Missing shares triggers error."""
        rows = [{"ticker": "AAPL", "shares": ""}]
        valid, errors = validate_required_fields(rows)
        assert len(valid) == 0
        assert len(errors) == 1
        assert errors[0]["field"] == "shares"


# ── TestNormalize ─────────────────────────────────────────────────────


class TestNormalize:
    """Tests for normalize_tickers."""

    def test_lowercase_to_upper(self):
        """Convert lowercase tickers to uppercase."""
        rows = [{"ticker": "aapl"}, {"ticker": "msft"}]
        result = normalize_tickers(rows)
        assert result[0]["ticker"] == "AAPL"
        assert result[1]["ticker"] == "MSFT"

    def test_whitespace_stripped(self):
        """Strip whitespace from tickers."""
        rows = [{"ticker": "  GOOG  "}]
        result = normalize_tickers(rows)
        assert result[0]["ticker"] == "GOOG"

    def test_brk_b_preserved(self):
        """BRK.B ticker preserved correctly."""
        rows = [{"ticker": "brk.b"}]
        result = normalize_tickers(rows)
        assert result[0]["ticker"] == "BRK.B"


# ── TestDuplicates ────────────────────────────────────────────────────


class TestDuplicates:
    """Tests for detect_duplicates."""

    def test_no_duplicates(self):
        """No duplicate tickers."""
        rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}, {"ticker": "GOOG"}]
        dupes = detect_duplicates(rows)
        assert len(dupes) == 0

    def test_two_aapl_entries(self):
        """Two AAPL entries detected."""
        rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}, {"ticker": "AAPL"}]
        dupes = detect_duplicates(rows)
        assert len(dupes) == 1
        assert dupes[0]["ticker"] == "AAPL"
        assert dupes[0]["count"] == 2

    def test_three_way_dupe(self):
        """Three entries of the same ticker."""
        rows = [{"ticker": "XYZ"}, {"ticker": "XYZ"}, {"ticker": "XYZ"}]
        dupes = detect_duplicates(rows)
        assert len(dupes) == 1
        assert dupes[0]["count"] == 3


# ── TestNumeric ───────────────────────────────────────────────────────


class TestNumeric:
    """Tests for validate_numeric_fields."""

    def test_all_valid(self):
        """All numeric fields valid."""
        rows = [
            {"ticker": "AAPL", "shares": "100", "cost_basis": "150"},
            {"ticker": "MSFT", "shares": "80", "cost_basis": "300"},
        ]
        valid, errors = validate_numeric_fields(rows)
        assert len(valid) == 2
        assert len(errors) == 0

    def test_negative_shares(self):
        """Negative shares triggers error."""
        rows = [{"ticker": "AAPL", "shares": "-50", "cost_basis": "150"}]
        valid, errors = validate_numeric_fields(rows)
        assert len(valid) == 0
        assert len(errors) == 1
        assert errors[0]["field"] == "shares"

    def test_zero_cost(self):
        """Zero cost basis is valid (e.g., gifted shares)."""
        rows = [{"ticker": "AAPL", "shares": "100", "cost_basis": "0"}]
        valid, errors = validate_numeric_fields(rows)
        assert len(valid) == 1
        assert len(errors) == 0

    def test_string_in_numeric(self):
        """Non-numeric string in shares triggers error."""
        rows = [{"ticker": "AAPL", "shares": "abc", "cost_basis": "150"}]
        valid, errors = validate_numeric_fields(rows)
        assert len(valid) == 0
        assert len(errors) == 1
        assert "numeric" in errors[0]["message"].lower()


# ── TestUploadSummary ─────────────────────────────────────────────────


class TestUploadSummary:
    """Tests for compute_upload_summary."""

    def test_all_matched(self):
        """10/10 matched."""
        summary = compute_upload_summary(10, 10, 0, [])
        assert summary["total_rows"] == 10
        assert summary["matched_pct"] == 100.0
        assert summary["error_count"] == 0

    def test_partial_match(self):
        """8/10 matched."""
        summary = compute_upload_summary(10, 8, 2, [{"msg": "err"}])
        assert summary["matched_pct"] == 80.0
        assert summary["unmatched_tickers"] == 2
        assert summary["error_count"] == 1

    def test_zero_matched(self):
        """0/5 matched."""
        summary = compute_upload_summary(5, 0, 5, [])
        assert summary["matched_pct"] == 0.0


# ── TestCloseMatches ──────────────────────────────────────────────────


class TestCloseMatches:
    """Tests for suggest_close_matches."""

    def test_appl_suggests_aapl(self):
        """APPL → suggests AAPL."""
        known = ["AAPL", "MSFT", "GOOG", "AMZN"]
        suggestions = suggest_close_matches("APPL", known)
        assert "AAPL" in suggestions

    def test_exact_match(self):
        """MSFT exact → suggests MSFT."""
        known = ["AAPL", "MSFT", "GOOG"]
        suggestions = suggest_close_matches("MSFT", known)
        assert "MSFT" in suggestions

    def test_no_close_match(self):
        """Completely different ticker → no suggestions."""
        known = ["AAPL", "MSFT", "GOOG"]
        suggestions = suggest_close_matches("ZZZZZZZZZ", known)
        assert len(suggestions) == 0


# ── TestBuildPositions ────────────────────────────────────────────────


class TestBuildPositions:
    """Tests for build_position_list."""

    def test_five_valid_rows(self):
        """Build positions from 5 valid rows."""
        rows = parse_csv_holdings(_standard_csv())
        positions = build_position_list(rows)
        assert len(positions) == 5
        assert positions[0]["ticker"] == "AAPL"
        assert positions[0]["shares"] == 100.0

    def test_positions_have_required_fields(self):
        """Each position has ticker, shares, cost_basis_per_share, acquisition_date."""
        rows = parse_csv_holdings(_standard_csv())
        positions = build_position_list(rows)
        for pos in positions:
            assert "ticker" in pos
            assert "shares" in pos
            assert "cost_basis_per_share" in pos
            assert "acquisition_date" in pos


# ── TestErrorReport ───────────────────────────────────────────────────


class TestErrorReport:
    """Tests for generate_upload_error_report."""

    def test_three_errors(self):
        """Format 3 errors."""
        errors = [
            {"row": 1, "field": "ticker", "message": "Missing ticker"},
            {"row": 3, "field": "shares", "message": "Negative shares"},
            {"row": 5, "field": "cost_basis", "message": "Non-numeric"},
        ]
        report = generate_upload_error_report(errors)
        assert len(report) == 3
        assert report[0]["row"] == 1
        assert report[1]["field"] == "shares"

    def test_empty_errors(self):
        """No errors → empty report."""
        report = generate_upload_error_report([])
        assert report == []


# ── TestDateParse ─────────────────────────────────────────────────────


class TestDateParse:
    """Tests for parse_date_flexible."""

    def test_iso_format(self):
        """YYYY-MM-DD format."""
        assert parse_date_flexible("2024-06-15") == "2024-06-15"

    def test_us_format(self):
        """MM/DD/YYYY format."""
        assert parse_date_flexible("06/15/2024") == "2024-06-15"

    def test_short_year(self):
        """M/D/YY format."""
        result = parse_date_flexible("1/5/24")
        assert result == "2024-01-05"

    def test_invalid_date(self):
        """Invalid date string → None."""
        assert parse_date_flexible("not-a-date") is None
