"""D11.5 Credit Rating Analytics: numeric scales, notch computation, fallen angel/rising star detection."""

# Numeric scale: 1 = AAA (safest) to 22 = D (default)
SP_SCALE = {
    "AAA": 1, "AA+": 2, "AA": 3, "AA-": 4,
    "A+": 5, "A": 6, "A-": 7,
    "BBB+": 8, "BBB": 9, "BBB-": 10,
    "BB+": 11, "BB": 12, "BB-": 13,
    "B+": 14, "B": 15, "B-": 16,
    "CCC+": 17, "CCC": 18, "CCC-": 19,
    "CC": 20, "C": 21, "D": 22,
}

MOODYS_SCALE = {
    "Aaa": 1, "Aa1": 2, "Aa2": 3, "Aa3": 4,
    "A1": 5, "A2": 6, "A3": 7,
    "Baa1": 8, "Baa2": 9, "Baa3": 10,
    "Ba1": 11, "Ba2": 12, "Ba3": 13,
    "B1": 14, "B2": 15, "B3": 16,
    "Caa1": 17, "Caa2": 18, "Caa3": 19,
    "Ca": 20, "C": 21, "D": 22,
}

FITCH_SCALE = {
    "AAA": 1, "AA+": 2, "AA": 3, "AA-": 4,
    "A+": 5, "A": 6, "A-": 7,
    "BBB+": 8, "BBB": 9, "BBB-": 10,
    "BB+": 11, "BB": 12, "BB-": 13,
    "B+": 14, "B": 15, "B-": 16,
    "CCC+": 17, "CCC": 18, "CCC-": 19,
    "CC": 20, "C": 21, "D": 22,
}

# Reverse maps for numeric -> letter
SP_REVERSE = {v: k for k, v in SP_SCALE.items()}
MOODYS_REVERSE = {v: k for k, v in MOODYS_SCALE.items()}
FITCH_REVERSE = {v: k for k, v in FITCH_SCALE.items()}

AGENCY_SCALES = {"SP": SP_SCALE, "MOODYS": MOODYS_SCALE, "FITCH": FITCH_SCALE}
AGENCY_REVERSE = {"SP": SP_REVERSE, "MOODYS": MOODYS_REVERSE, "FITCH": FITCH_REVERSE}

# IG/HY boundary: numeric 10 = BBB-/Baa3 (last IG), 11 = BB+/Ba1 (first HY)
IG_HY_BOUNDARY = 10


def rating_to_numeric(agency: str, letter_rating: str) -> int | None:
    """Convert a letter rating to its numeric equivalent on the agency's scale."""
    scale = AGENCY_SCALES.get(agency.upper())
    if not scale:
        return None
    return scale.get(letter_rating)


def numeric_to_rating(agency: str, numeric: int) -> str | None:
    """Convert a numeric rating back to its letter equivalent."""
    reverse = AGENCY_REVERSE.get(agency.upper())
    if not reverse:
        return None
    return reverse.get(numeric)


def compute_notches(old_numeric: int | None, new_numeric: int | None) -> int | None:
    """Compute the number of notches changed. Positive = upgrade."""
    if old_numeric is None or new_numeric is None:
        return None
    return old_numeric - new_numeric  # positive = upgrade


def is_fallen_angel(old_numeric: int | None, new_numeric: int | None) -> bool:
    """Detect fallen angel: downgrade from IG to HY."""
    if old_numeric is None or new_numeric is None:
        return False
    return old_numeric <= IG_HY_BOUNDARY and new_numeric > IG_HY_BOUNDARY


def is_rising_star(old_numeric: int | None, new_numeric: int | None) -> bool:
    """Detect rising star: upgrade from HY to IG."""
    if old_numeric is None or new_numeric is None:
        return False
    return old_numeric > IG_HY_BOUNDARY and new_numeric <= IG_HY_BOUNDARY


def is_investment_grade(numeric: int | None) -> bool | None:
    """Determine if a numeric rating is investment grade."""
    if numeric is None:
        return None
    return numeric <= IG_HY_BOUNDARY


def compute_migration_matrix(events: list[dict]) -> dict:
    """Compute rating transition matrix from events.

    Each event dict should have 'old_rating' and 'new_rating' keys.
    Returns a nested dict: matrix[old_rating][new_rating] = count.
    """
    matrix: dict[str, dict[str, int]] = {}
    for e in events:
        old = e.get("old_rating", "")
        new = e.get("new_rating", "")
        if not old or not new:
            continue
        if old not in matrix:
            matrix[old] = {}
        matrix[old][new] = matrix[old].get(new, 0) + 1
    return matrix


def average_rating_numeric(ratings: list[int]) -> float | None:
    """Compute the average numeric rating from a list of numeric ratings."""
    if not ratings:
        return None
    return sum(ratings) / len(ratings)
