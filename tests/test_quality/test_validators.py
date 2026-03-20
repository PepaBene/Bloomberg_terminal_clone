"""Tests for data quality validators."""

import pytest

from src.quality.validators import _luhn_checksum


class TestISINValidation:
    def test_valid_isin_apple(self):
        """Apple Inc ISIN should pass validation."""
        assert _luhn_checksum("US0378331005") is True

    def test_valid_isin_microsoft(self):
        """Microsoft ISIN should pass validation."""
        assert _luhn_checksum("US5949181045") is True

    def test_invalid_isin_bad_check_digit(self):
        """ISIN with wrong check digit should fail."""
        assert _luhn_checksum("US0378331009") is False

    def test_invalid_isin_too_short(self):
        """ISIN that's too short should fail."""
        assert _luhn_checksum("US037833100") is False

    def test_invalid_isin_too_long(self):
        """ISIN that's too long should fail."""
        assert _luhn_checksum("US03783310051") is False

    def test_valid_isin_german(self):
        """Siemens AG ISIN should pass."""
        assert _luhn_checksum("DE0007236101") is True
