"""Portfolio Parser Engine.

Parses CSV/Excel portfolio files and matches holdings to securities.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field


@dataclass
class ParsedHolding:
    """A single holding parsed from a portfolio file."""
    row_number: int
    identifier: str | None = None
    name: str | None = None
    quantity: float | None = None
    weight: float | None = None
    raw_data: dict = field(default_factory=dict)


def parse_csv(content: str) -> list[ParsedHolding]:
    """Parse a CSV string into a list of parsed holdings.

    Expected columns (case-insensitive):
    - ticker, symbol, or identifier → identifier
    - name, security_name, company → name
    - quantity, shares, qty → quantity
    - weight, pct, allocation → weight
    """
    holdings = []
    reader = csv.DictReader(io.StringIO(content))

    try:
        # Normalize column names
        if reader.fieldnames is None:
            return []

        col_map = _build_column_map(reader.fieldnames)

        for row_num, row in enumerate(reader, start=2):  # row 1 is header
            holding = ParsedHolding(row_number=row_num, raw_data=dict(row))

            if col_map.get("identifier"):
                holding.identifier = row.get(col_map["identifier"], "").strip() or None
            if col_map.get("name"):
                holding.name = row.get(col_map["name"], "").strip() or None
            if col_map.get("quantity"):
                holding.quantity = _safe_float(row.get(col_map["quantity"]))
            if col_map.get("weight"):
                holding.weight = _safe_float(row.get(col_map["weight"]))

            # Skip empty rows
            if holding.identifier or holding.name:
                holdings.append(holding)
    except csv.Error as exc:
        # Malformed CSV (e.g. unterminated quote, inconsistent quoting)
        # raises _csv.Error mid-iteration. Surface it as a ValueError so the
        # API layer's ValueError handler turns it into a 422 validation
        # error instead of an opaque 500.
        raise ValueError(f"Malformed CSV content: {exc}") from exc

    return holdings


def _build_column_map(fieldnames: list[str]) -> dict[str, str]:
    """Map semantic field names to actual column names."""
    mapping = {}
    for col in fieldnames:
        lower = col.lower().strip()
        if lower in ("ticker", "symbol", "identifier", "isin", "cusip", "sedol"):
            mapping["identifier"] = col
        elif lower in ("name", "security_name", "company", "security"):
            mapping["name"] = col
        elif lower in ("quantity", "shares", "qty", "amount"):
            mapping["quantity"] = col
        elif lower in ("weight", "pct", "allocation", "percent", "%"):
            mapping["weight"] = col
    return mapping


def _safe_float(value: str | None) -> float | None:
    """Try to convert a string to float, returning None on failure."""
    if value is None:
        return None
    try:
        cleaned = value.strip().replace(",", "").replace("%", "")
        if not cleaned:
            return None
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


@dataclass
class MatchResult:
    """Result of matching a holding to a security."""
    row_number: int
    identifier: str | None
    name: str | None
    status: str  # MATCHED, AMBIGUOUS, NOT_FOUND
    matched_security_id: str | None = None
    confidence: float = 0.0


def match_holdings_to_securities(
    holdings: list[ParsedHolding],
    known_tickers: dict[str, str] | None = None,
    known_names: dict[str, str] | None = None,
) -> list[MatchResult]:
    """Match parsed holdings against known securities.

    Parameters
    ----------
    holdings : Parsed holdings from CSV/Excel.
    known_tickers : {ticker → security_id} lookup.
    known_names : {name_lower → security_id} lookup.

    Returns
    -------
    list of MatchResult
    """
    results = []
    tickers = known_tickers or {}
    names = known_names or {}

    for h in holdings:
        # Try ticker match first
        if h.identifier and h.identifier.upper() in tickers:
            results.append(MatchResult(
                row_number=h.row_number,
                identifier=h.identifier,
                name=h.name,
                status="MATCHED",
                matched_security_id=tickers[h.identifier.upper()],
                confidence=1.0,
            ))
            continue

        # Try name match
        if h.name and h.name.lower() in names:
            results.append(MatchResult(
                row_number=h.row_number,
                identifier=h.identifier,
                name=h.name,
                status="MATCHED",
                matched_security_id=names[h.name.lower()],
                confidence=0.8,
            ))
            continue

        # No match
        results.append(MatchResult(
            row_number=h.row_number,
            identifier=h.identifier,
            name=h.name,
            status="NOT_FOUND",
        ))

    return results
