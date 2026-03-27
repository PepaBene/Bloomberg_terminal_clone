"""Tests for the Credit Rating Analytics engine (D11 FI Supplement P5)."""

import pytest

from src.engines.credit_rating_analytics import (
    average_rating_numeric,
    compute_migration_matrix,
    compute_notches,
    is_fallen_angel,
    is_investment_grade,
    is_rising_star,
    numeric_to_rating,
    rating_to_numeric,
)


# ── rating_to_numeric ──────────────────────────────────────────────


class TestRatingToNumeric:
    def test_sp_rating_to_numeric(self):
        """SP: AAA -> 1, BBB- -> 10, D -> 22."""
        assert rating_to_numeric("SP", "AAA") == 1
        assert rating_to_numeric("SP", "BBB-") == 10
        assert rating_to_numeric("SP", "D") == 22

    def test_moodys_rating_to_numeric(self):
        """Moody's: Aaa -> 1, Baa3 -> 10."""
        assert rating_to_numeric("MOODYS", "Aaa") == 1
        assert rating_to_numeric("MOODYS", "Baa3") == 10

    def test_fitch_rating_to_numeric(self):
        """Fitch: AA+ -> 2."""
        assert rating_to_numeric("FITCH", "AA+") == 2

    def test_rating_unknown(self):
        """Unknown rating letter returns None."""
        assert rating_to_numeric("SP", "XYZ") is None

    def test_rating_unknown_agency(self):
        """Unknown agency returns None."""
        assert rating_to_numeric("DBRS", "AAA") is None


# ── numeric_to_rating ──────────────────────────────────────────────


class TestNumericToRating:
    def test_numeric_to_rating_sp(self):
        """SP: 1 -> AAA, 10 -> BBB-."""
        assert numeric_to_rating("SP", 1) == "AAA"
        assert numeric_to_rating("SP", 10) == "BBB-"

    def test_numeric_to_rating_moodys(self):
        """Moody's: 10 -> Baa3."""
        assert numeric_to_rating("MOODYS", 10) == "Baa3"

    def test_numeric_to_rating_unknown(self):
        """Unknown numeric returns None."""
        assert numeric_to_rating("SP", 99) is None


# ── compute_notches ────────────────────────────────────────────────


class TestComputeNotches:
    def test_compute_notches_upgrade(self):
        """old=10, new=8 -> +2 (upgrade by 2 notches)."""
        assert compute_notches(10, 8) == 2

    def test_compute_notches_downgrade(self):
        """old=8, new=12 -> -4 (downgrade by 4 notches)."""
        assert compute_notches(8, 12) == -4

    def test_compute_notches_none(self):
        """None inputs -> None."""
        assert compute_notches(None, 8) is None
        assert compute_notches(10, None) is None
        assert compute_notches(None, None) is None


# ── is_fallen_angel / is_rising_star ───────────────────────────────


class TestCrossoverFlags:
    def test_fallen_angel(self):
        """old=10 (BBB-), new=11 (BB+) -> True (crossed IG/HY boundary)."""
        assert is_fallen_angel(10, 11) is True

    def test_not_fallen_angel(self):
        """old=8, new=10 -> False (still IG)."""
        assert is_fallen_angel(8, 10) is False

    def test_fallen_angel_none(self):
        """None inputs -> False."""
        assert is_fallen_angel(None, 11) is False

    def test_rising_star(self):
        """old=11 (BB+), new=10 (BBB-) -> True."""
        assert is_rising_star(11, 10) is True

    def test_not_rising_star(self):
        """old=12, new=11 -> False (still HY)."""
        assert is_rising_star(12, 11) is False

    def test_rising_star_none(self):
        """None inputs -> False."""
        assert is_rising_star(None, 10) is False


# ── is_investment_grade ────────────────────────────────────────────


class TestIsInvestmentGrade:
    def test_ig_boundary(self):
        """10 (BBB-) -> True, 11 (BB+) -> False."""
        assert is_investment_grade(10) is True
        assert is_investment_grade(11) is False

    def test_ig_none(self):
        """None -> None."""
        assert is_investment_grade(None) is None


# ── compute_migration_matrix ───────────────────────────────────────


class TestMigrationMatrix:
    def test_migration_matrix(self):
        """5 events should yield correct counts."""
        events = [
            {"old_rating": "BBB", "new_rating": "BBB+"},
            {"old_rating": "BBB", "new_rating": "BBB-"},
            {"old_rating": "BBB", "new_rating": "BBB+"},
            {"old_rating": "A-", "new_rating": "BBB+"},
            {"old_rating": "A-", "new_rating": "A"},
        ]
        matrix = compute_migration_matrix(events)
        assert matrix["BBB"]["BBB+"] == 2
        assert matrix["BBB"]["BBB-"] == 1
        assert matrix["A-"]["BBB+"] == 1
        assert matrix["A-"]["A"] == 1

    def test_migration_matrix_empty(self):
        """Empty events -> empty matrix."""
        assert compute_migration_matrix([]) == {}

    def test_migration_matrix_skip_missing(self):
        """Events without old/new ratings are skipped."""
        events = [
            {"old_rating": "BBB", "new_rating": ""},
            {"old_rating": "", "new_rating": "A"},
            {"new_rating": "A"},
        ]
        assert compute_migration_matrix(events) == {}


# ── average_rating_numeric ─────────────────────────────────────────


class TestAverageRating:
    def test_average(self):
        """Average of [8, 9, 10] = 9.0."""
        assert average_rating_numeric([8, 9, 10]) == 9.0

    def test_average_empty(self):
        """Empty list -> None."""
        assert average_rating_numeric([]) is None
