"""Tests for entity name normalization."""

import pytest

from src.resolution.normalizer import normalize_name, strip_suffixes


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("APPLE INC.") == "apple inc"

    def test_strip_punctuation(self):
        assert normalize_name("Johnson & Johnson") == "johnson johnson"

    def test_collapse_spaces(self):
        assert normalize_name("  Apple   Inc  ") == "apple inc"

    def test_unicode_normalization(self):
        # Accented characters should be decomposed
        result = normalize_name("Société Générale")
        assert "societe" in result


class TestStripSuffixes:
    def test_strip_inc(self):
        result = strip_suffixes("apple inc")
        assert result.strip() == "apple"

    def test_strip_corporation(self):
        result = strip_suffixes("microsoft corporation")
        assert result.strip() == "microsoft"

    def test_strip_llc(self):
        result = strip_suffixes("google llc")
        assert result.strip() == "google"

    def test_strip_ltd(self):
        result = strip_suffixes("barclays ltd")
        assert result.strip() == "barclays"

    def test_strip_plc(self):
        result = strip_suffixes("bp plc")
        assert result.strip() == "bp"

    def test_no_suffix(self):
        result = strip_suffixes("alphabet")
        assert result.strip() == "alphabet"
