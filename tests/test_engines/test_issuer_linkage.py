"""Tests for the Issuer Linkage engine (D11 FI Supplement P9)."""

from src.engines.issuer_linkage import (
    detect_financing_subsidiary,
    resolve_issuer_to_parent,
    build_issuer_bond_hierarchy,
)


# ── detect_financing_subsidiary ───────────────────────────────────


class TestDetectFinancingSubsidiary:
    def test_detect_capital(self):
        """'Apple Capital LLC' should be detected as financing subsidiary."""
        assert detect_financing_subsidiary("Apple Capital LLC") is True

    def test_detect_funding(self):
        """'Microsoft Funding Corp' should be detected."""
        assert detect_financing_subsidiary("Microsoft Funding Corp") is True

    def test_detect_finance(self):
        """'GE Finance' should be detected."""
        assert detect_financing_subsidiary("GE Finance") is True

    def test_detect_treasury(self):
        """'Ford Treasury Ltd' should be detected (Treasury pattern)."""
        assert detect_financing_subsidiary("Ford Treasury Ltd") is True

    def test_detect_issuer(self):
        """'BMW Issuer GmbH' should be detected (Issuer pattern)."""
        assert detect_financing_subsidiary("BMW Issuer GmbH") is True

    def test_detect_normal(self):
        """'Apple Inc' is not a financing subsidiary."""
        assert detect_financing_subsidiary("Apple Inc") is False

    def test_detect_empty(self):
        """Empty string returns False."""
        assert detect_financing_subsidiary("") is False

    def test_detect_case_insensitive(self):
        """Detection is case-insensitive."""
        assert detect_financing_subsidiary("acme CAPITAL corp") is True


# ── resolve_issuer_to_parent ──────────────────────────────────────


class TestResolveIssuerToParent:
    def test_resolve_to_parent(self):
        """'Apple Capital LLC' should match 'Apple Inc' from candidates."""
        candidates = [
            {"entity_id": "aaa", "legal_name": "Apple Inc"},
            {"entity_id": "bbb", "legal_name": "Microsoft Corp"},
        ]
        result = resolve_issuer_to_parent("Apple Capital LLC", candidates)
        assert result is not None
        assert result["entity_id"] == "aaa"

    def test_resolve_no_match(self):
        """'XYZ Corp' with unrelated candidates returns None."""
        candidates = [
            {"entity_id": "aaa", "legal_name": "Apple Inc"},
            {"entity_id": "bbb", "legal_name": "Microsoft Corp"},
        ]
        result = resolve_issuer_to_parent("XYZ Corp", candidates)
        assert result is None

    def test_resolve_empty_candidates(self):
        """Empty candidates list returns None."""
        result = resolve_issuer_to_parent("Apple Capital LLC", [])
        assert result is None

    def test_resolve_empty_name(self):
        """Empty issuer name returns None."""
        candidates = [{"entity_id": "aaa", "legal_name": "Apple Inc"}]
        result = resolve_issuer_to_parent("", candidates)
        assert result is None

    def test_resolve_best_match(self):
        """Should pick the best matching candidate by score."""
        candidates = [
            {"entity_id": "aaa", "legal_name": "JP"},
            {"entity_id": "bbb", "legal_name": "JPMorgan Chase"},
        ]
        result = resolve_issuer_to_parent("JPMorgan Chase Capital LLC", candidates)
        assert result is not None
        assert result["entity_id"] == "bbb"


# ── build_issuer_bond_hierarchy ───────────────────────────────────


class TestBuildIssuerBondHierarchy:
    def test_hierarchy_simple(self):
        """Parent + 1 subsidiary + bonds -> correct tree."""
        parent = {"entity_id": "p1", "legal_name": "Apple Inc"}
        subs = [{"entity_id": "s1", "legal_name": "Apple Capital LLC"}]
        bonds_by_entity = {
            "p1": [{"cusip": "037833AK6", "name": "Apple 5% 2035"}],
            "s1": [{"cusip": "037833BL7", "name": "Apple Capital 4% 2030"}],
        }
        result = build_issuer_bond_hierarchy(parent, subs, bonds_by_entity)

        assert result["entity_id"] == "p1"
        assert result["legal_name"] == "Apple Inc"
        assert len(result["bonds"]) == 1
        assert result["bonds"][0]["cusip"] == "037833AK6"
        assert len(result["subsidiaries"]) == 1
        assert result["subsidiaries"][0]["entity_id"] == "s1"
        assert len(result["subsidiaries"][0]["bonds"]) == 1

    def test_hierarchy_no_subsidiaries(self):
        """Parent with no subsidiaries -> empty subsidiaries list."""
        parent = {"entity_id": "p1", "legal_name": "Solo Corp"}
        bonds_by_entity = {
            "p1": [{"cusip": "111111AA1", "name": "Solo 3% 2028"}],
        }
        result = build_issuer_bond_hierarchy(parent, [], bonds_by_entity)

        assert result["entity_id"] == "p1"
        assert result["subsidiaries"] == []
        assert len(result["bonds"]) == 1

    def test_hierarchy_no_bonds(self):
        """Parent with subsidiary but no bonds anywhere."""
        parent = {"entity_id": "p1", "legal_name": "Empty Corp"}
        subs = [{"entity_id": "s1", "legal_name": "Empty Capital LLC"}]
        result = build_issuer_bond_hierarchy(parent, subs, {})

        assert result["bonds"] == []
        assert result["subsidiaries"][0]["bonds"] == []
