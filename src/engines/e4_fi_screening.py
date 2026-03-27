"""E4 Extension: Fixed Income Bond Screening.

Provides filtering and ranking for corporate bonds using
CorporateBond and BondEODPrice data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


# ---------------------------------------------------------------------------
# Rating mapping (S&P scale to numeric)
# ---------------------------------------------------------------------------

_RATING_TO_NUMERIC: dict[str, int] = {
    "AAA": 1,
    "AA+": 2,
    "AA": 3,
    "AA-": 4,
    "A+": 5,
    "A": 6,
    "A-": 7,
    "BBB+": 8,
    "BBB": 9,
    "BBB-": 10,
    "BB+": 11,
    "BB": 12,
    "BB-": 13,
    "B+": 14,
    "B": 15,
    "B-": 16,
    "CCC+": 17,
    "CCC": 18,
    "CCC-": 19,
    "CC": 20,
    "C": 21,
    "D": 22,
}

# Investment grade threshold (BBB- = 10)
_IG_THRESHOLD = 10


def rating_to_numeric(rating: str | None) -> int | None:
    """Convert an S&P-style rating string to a numeric value (1=AAA, 22=D).

    Returns ``None`` for unrecognised / missing ratings.
    """
    if rating is None:
        return None
    return _RATING_TO_NUMERIC.get(rating.strip().upper())


# ---------------------------------------------------------------------------
# Filter dataclass
# ---------------------------------------------------------------------------

@dataclass
class BondScreenFilter:
    """Filter criterion for bond screening."""

    field: str
    op: str  # GT, LT, GTE, LTE, EQ, BETWEEN, IN
    value: float | str | None = None
    value2: float | str | None = None


# ---------------------------------------------------------------------------
# Available filter fields
# ---------------------------------------------------------------------------

BOND_SCREEN_FIELDS = {
    "spread_bps": "BondEODPrice.g_spread_bps",
    "yield_to_worst": "BondEODPrice.yield_to_worst",
    "yield_to_maturity": "BondEODPrice.yield_to_maturity",
    "modified_duration": "computed",
    "liquidity_score": "BondEODPrice.liquidity_score",
    "rating_numeric": "CorporateBond.initial_rating_sp mapped to numeric",
    "coupon_rate": "CorporateBond.coupon_rate",
    "maturity_date": "CorporateBond.maturity_date",
    "seniority": "CorporateBond.seniority",
    "is_callable": "CorporateBond.callable",
    "is_investment_grade": "CorporateBond.is_investment_grade",
    "outstanding_amount": "CorporateBond.outstanding_amount",
}


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _coerce(value, reference):
    """Coerce *value* to the same type as *reference* when possible."""
    if reference is None:
        return value
    if isinstance(reference, bool):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)
    if isinstance(reference, (int, float)):
        try:
            return float(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            return value
    if isinstance(reference, date):
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value
    return value


def _compare(field_value, op: str, value, value2=None) -> bool:
    """Evaluate a single comparison.  Returns ``True`` if the bond passes."""
    if field_value is None:
        return False

    v = _coerce(value, field_value)

    op = op.upper()

    if op == "GT":
        return field_value > v
    if op == "LT":
        return field_value < v
    if op == "GTE":
        return field_value >= v
    if op == "LTE":
        return field_value <= v
    if op == "EQ":
        # Case-insensitive for strings
        if isinstance(field_value, str) and isinstance(v, str):
            return field_value.upper() == v.upper()
        return field_value == v
    if op == "BETWEEN":
        v2 = _coerce(value2, field_value)
        if v2 is None:
            return False
        lo, hi = (v, v2) if v <= v2 else (v2, v)
        return lo <= field_value <= hi
    if op == "IN":
        # value should be a list, or a comma-separated string
        if isinstance(value, str):
            options = [s.strip() for s in value.split(",")]
        elif isinstance(value, (list, tuple)):
            options = list(value)
        else:
            options = [value]
        if isinstance(field_value, str):
            return field_value.upper() in [str(o).upper() for o in options]
        return field_value in options

    # Unknown operator — fail open (exclude)
    return False


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def apply_bond_filters(
    bonds: list[dict],
    filters: list[BondScreenFilter],
) -> list[dict]:
    """Apply filters to a list of bond dicts (AND logic).

    Each bond dict has keys matching ``BOND_SCREEN_FIELDS``.
    Returns the filtered list (order preserved).
    """
    if not filters:
        return list(bonds)

    result: list[dict] = []
    for bond in bonds:
        passes = True
        for f in filters:
            field_value = bond.get(f.field)
            if not _compare(field_value, f.op, f.value, f.value2):
                passes = False
                break
        if passes:
            result.append(bond)
    return result


def rank_bonds(
    bonds: list[dict],
    sort_field: str = "spread_bps",
    ascending: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Rank and limit bond results.

    Bonds missing the ``sort_field`` are placed at the end.
    """
    def _sort_key(b: dict):
        v = b.get(sort_field)
        if v is None:
            # Push None items to end regardless of sort direction
            return (1, 0)
        if ascending:
            return (0, v)
        else:
            # For descending, negate to get natural descending while keeping
            # None (sentinel=1) always at the end
            try:
                return (0, -v)
            except TypeError:
                return (0, v)

    sorted_bonds = sorted(bonds, key=_sort_key)
    return sorted_bonds[:limit]
