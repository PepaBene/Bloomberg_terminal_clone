"""Pillar 4 Phase 1 — CSV/Excel Upload Parsing Engine.

Pure computation engine for parsing, validating, normalizing, and
summarizing portfolio uploads from CSV files.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime


# ── CSV Parsing ─────────────────────────────────────────────────────────


def parse_csv_holdings(
    csv_content: str,
    delimiter: str = ",",
) -> list[dict]:
    """Parse CSV content into a list of row dicts.

    Parameters
    ----------
    csv_content : str
        Raw CSV text content.
    delimiter : str
        Field delimiter (default comma).

    Returns
    -------
    list[dict]
        One dict per row, keys from the header.
    """
    if not csv_content.strip():
        return []

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
    rows: list[dict] = []
    for row in reader:
        rows.append(dict(row))
    return rows


# ── Field Validation ────────────────────────────────────────────────────


REQUIRED_FIELDS = {"ticker", "shares"}


def validate_required_fields(
    rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Validate that each row has required fields (ticker, shares).

    Returns
    -------
    tuple[list[dict], list[dict]]
        (valid_rows, error_rows). Each error row has {row, field, message}.
    """
    valid: list[dict] = []
    errors: list[dict] = []

    for i, row in enumerate(rows, start=1):
        row_errors: list[dict] = []
        # Normalize keys to lowercase for comparison
        lower_keys = {k.lower().strip(): k for k in row.keys()}

        has_ticker = False
        has_shares = False

        for req in REQUIRED_FIELDS:
            if req in lower_keys:
                val = row[lower_keys[req]]
                if val is None or str(val).strip() == "":
                    row_errors.append({
                        "row": i,
                        "field": req,
                        "message": f"Missing required field: {req}",
                    })
                else:
                    if req == "ticker":
                        has_ticker = True
                    elif req == "shares":
                        has_shares = True
            else:
                row_errors.append({
                    "row": i,
                    "field": req,
                    "message": f"Missing required field: {req}",
                })

        if row_errors:
            errors.extend(row_errors)
        else:
            valid.append(row)

    return valid, errors


# ── Ticker Normalization ───────────────────────────────────────────────


def normalize_tickers(rows: list[dict]) -> list[dict]:
    """Normalize ticker symbols: uppercase, strip whitespace.

    Handles special tickers like BRK.B, BF.B correctly.
    """
    normalized: list[dict] = []
    for row in rows:
        new_row = dict(row)
        # Find the ticker key (case-insensitive)
        for key in row:
            if key.lower().strip() == "ticker":
                raw = str(row[key]).strip().upper()
                new_row[key] = raw
                break
        normalized.append(new_row)
    return normalized


# ── Duplicate Detection ────────────────────────────────────────────────


def detect_duplicates(rows: list[dict]) -> list[dict]:
    """Detect duplicate ticker entries.

    Returns
    -------
    list[dict]
        List of {ticker, count, row_indices} for tickers appearing > 1 time.
    """
    ticker_map: dict[str, list[int]] = {}

    for i, row in enumerate(rows, start=1):
        ticker = None
        for key in row:
            if key.lower().strip() == "ticker":
                ticker = str(row[key]).strip().upper()
                break
        if ticker:
            if ticker not in ticker_map:
                ticker_map[ticker] = []
            ticker_map[ticker].append(i)

    duplicates: list[dict] = []
    for ticker, indices in ticker_map.items():
        if len(indices) > 1:
            duplicates.append({
                "ticker": ticker,
                "count": len(indices),
                "row_indices": indices,
            })

    return duplicates


# ── Numeric Validation ─────────────────────────────────────────────────


def validate_numeric_fields(
    rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Validate numeric fields: shares > 0, cost_basis >= 0.

    Returns
    -------
    tuple[list[dict], list[dict]]
        (valid_rows, error_rows).
    """
    valid: list[dict] = []
    errors: list[dict] = []

    for i, row in enumerate(rows, start=1):
        row_errors: list[dict] = []

        # Find shares field
        shares_val = None
        for key in row:
            if key.lower().strip() == "shares":
                shares_val = row[key]
                break

        if shares_val is not None:
            try:
                shares_num = float(shares_val)
                if shares_num <= 0:
                    row_errors.append({
                        "row": i,
                        "field": "shares",
                        "message": f"Shares must be positive, got {shares_num}",
                    })
            except (ValueError, TypeError):
                row_errors.append({
                    "row": i,
                    "field": "shares",
                    "message": f"Shares must be numeric, got '{shares_val}'",
                })

        # Find cost_basis field (optional)
        cost_val = None
        for key in row:
            if key.lower().strip() in ("cost_basis", "cost_basis_per_share", "cost"):
                cost_val = row[key]
                break

        if cost_val is not None and str(cost_val).strip() != "":
            try:
                cost_num = float(cost_val)
                if cost_num < 0:
                    row_errors.append({
                        "row": i,
                        "field": "cost_basis",
                        "message": f"Cost basis must be non-negative, got {cost_num}",
                    })
            except (ValueError, TypeError):
                row_errors.append({
                    "row": i,
                    "field": "cost_basis",
                    "message": f"Cost basis must be numeric, got '{cost_val}'",
                })

        if row_errors:
            errors.extend(row_errors)
        else:
            valid.append(row)

    return valid, errors


# ── Upload Summary ─────────────────────────────────────────────────────


def compute_upload_summary(
    total: int,
    matched: int,
    unmatched: int,
    errors: list,
) -> dict:
    """Compute a summary of the upload process.

    Returns
    -------
    dict
        {total_rows, matched_pct, unmatched_tickers, error_count}
    """
    matched_pct = (matched / total * 100.0) if total > 0 else 0.0
    return {
        "total_rows": total,
        "matched_pct": round(matched_pct, 1),
        "unmatched_tickers": unmatched,
        "error_count": len(errors),
    }


# ── Ticker Matching / Suggestions ──────────────────────────────────────


def _edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[m][n]


def suggest_close_matches(
    ticker: str,
    known_tickers: list[str],
    max_suggestions: int = 3,
) -> list[str]:
    """Suggest close ticker matches using edit distance.

    Parameters
    ----------
    ticker : str
        The unmatched ticker.
    known_tickers : list[str]
        Known valid tickers.
    max_suggestions : int
        Maximum suggestions to return.

    Returns
    -------
    list[str]
        Up to max_suggestions tickers, sorted by edit distance.
    """
    if not known_tickers:
        return []

    ticker_upper = ticker.upper().strip()
    scored = [
        (kt, _edit_distance(ticker_upper, kt.upper()))
        for kt in known_tickers
    ]
    scored.sort(key=lambda x: x[1])

    # Only return matches within a reasonable edit distance
    max_dist = max(2, len(ticker_upper) // 2)
    return [
        s[0] for s in scored[:max_suggestions] if s[1] <= max_dist
    ]


# ── Position List Builder ──────────────────────────────────────────────


def build_position_list(validated_rows: list[dict]) -> list[dict]:
    """Convert validated rows to position dicts.

    Returns
    -------
    list[dict]
        Each: {ticker, shares, cost_basis_per_share, acquisition_date}.
    """
    positions: list[dict] = []
    for row in validated_rows:
        # Find fields case-insensitively
        ticker = None
        shares = None
        cost_basis = None
        acq_date = None

        for key, val in row.items():
            k = key.lower().strip()
            if k == "ticker":
                ticker = str(val).strip().upper()
            elif k == "shares":
                try:
                    shares = float(val)
                except (ValueError, TypeError):
                    shares = 0.0
            elif k in ("cost_basis", "cost_basis_per_share", "cost"):
                try:
                    cost_basis = float(val)
                except (ValueError, TypeError):
                    cost_basis = 0.0
            elif k in ("acquisition_date", "date", "purchase_date"):
                acq_date = str(val).strip() if val else None

        if ticker and shares:
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "cost_basis_per_share": cost_basis or 0.0,
                "acquisition_date": acq_date,
            })

    return positions


# ── Error Report Generator ─────────────────────────────────────────────


def generate_upload_error_report(errors: list[dict]) -> list[dict]:
    """Format errors into a structured report.

    Parameters
    ----------
    errors : list[dict]
        Each: {row, field, message}.

    Returns
    -------
    list[dict]
        Formatted error entries: {row, field, message}.
    """
    return [
        {
            "row": e.get("row", 0),
            "field": e.get("field", "unknown"),
            "message": e.get("message", "Unknown error"),
        }
        for e in errors
    ]


# ── Flexible Date Parsing ──────────────────────────────────────────────


def parse_date_flexible(date_str: str) -> str | None:
    """Parse a date string flexibly, returning YYYY-MM-DD or None.

    Supports: YYYY-MM-DD, MM/DD/YYYY, M/D/YY.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None
