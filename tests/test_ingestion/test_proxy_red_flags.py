"""Tests for src/ingestion/proxy_red_flags.py -- DEF 14A structural
governance red-flag text-mining (§4.7). Pure text functions, no I/O."""
from __future__ import annotations

from src.ingestion.proxy_red_flags import (
    extract_dual_class,
    extract_majority_voting,
    extract_poison_pill,
    extract_related_party,
    extract_staggered_board,
    mine_structural_red_flags,
)


class TestExtractDualClass:

    def test_detects_class_a_class_b_common_stock(self):
        text = "Our authorized capital stock consists of Class A common stock and Class B common stock."
        assert extract_dual_class(text) is True

    def test_detects_dual_class_structure_phrase(self):
        assert extract_dual_class("The Company maintains a dual-class structure.") is True

    def test_no_mention_returns_none(self):
        assert extract_dual_class("The Company has one class of common stock outstanding.") is None


class TestExtractPoisonPill:

    def test_detects_shareholder_rights_plan(self):
        text = "The Board adopted a shareholder rights plan in response to the unsolicited offer."
        assert extract_poison_pill(text) is True

    def test_detects_explicit_negation(self):
        text = "The Company does not have a poison pill or shareholder rights plan in effect."
        assert extract_poison_pill(text) is False

    def test_no_mention_returns_none(self):
        assert extract_poison_pill("The Company reported record revenue this quarter.") is None


class TestExtractStaggeredBoard:

    def test_detects_classified_board(self):
        text = "Our board of directors is divided into three classes with staggered terms."
        assert extract_staggered_board(text) is True

    def test_detects_negation(self):
        text = "The Company does not have a staggered board; all directors are elected annually."
        assert extract_staggered_board(text) is False

    def test_no_mention_returns_none(self):
        assert extract_staggered_board("Directors serve one-year terms.") is None


class TestExtractMajorityVoting:

    def test_detects_majority_voting_standard(self):
        text = "Directors are elected under a majority voting standard in uncontested elections."
        assert extract_majority_voting(text) is True

    def test_detects_plurality_voting_standard(self):
        text = "Directors are elected by a plurality voting standard."
        assert extract_majority_voting(text) is False

    def test_no_mention_returns_none(self):
        assert extract_majority_voting("The annual meeting will be held in June.") is None

    def test_both_mentioned_returns_none(self):
        text = (
            "Directors are elected under a majority voting standard in uncontested elections, "
            "except that a plurality voting standard applies in contested elections."
        )
        assert extract_majority_voting(text) is None


class TestExtractRelatedParty:

    def test_no_section_returns_none(self):
        assert extract_related_party("The Company's fiscal year ends December 31.") is None

    def test_explicit_none_reported(self):
        text = "There were no related party transactions during fiscal year 2025."
        assert extract_related_party(text) is False

    def test_transaction_with_dollar_amount_flagged(self):
        text = (
            "Related party transactions: the Company paid $2,500,000 to a firm "
            "owned by a director's immediate family member for consulting services."
        )
        assert extract_related_party(text) is True

    def test_section_present_but_ambiguous_returns_none(self):
        text = "Related party transactions are described under Item 404 of Regulation S-K."
        assert extract_related_party(text) is None


class TestMineStructuralRedFlags:

    def test_combines_all_five_when_evidence_present(self):
        text = (
            "Our authorized capital stock consists of Class A common stock and Class B common stock. "
            "The Board adopted a shareholder rights plan. "
            "Our board of directors is divided into three classes with staggered terms. "
            "Directors are elected under a majority voting standard in uncontested elections. "
            "Related party transactions: the Company paid $500,000 to an affiliate of a director."
        )
        result = mine_structural_red_flags(text)
        assert result == {
            "dual_class": True,
            "has_poison_pill": True,
            "has_staggered_board": True,
            "has_majority_voting": True,
            "related_party_flag": True,
        }

    def test_empty_text_returns_empty_dict(self):
        assert mine_structural_red_flags("") == {}

    def test_only_includes_keys_with_definite_evidence(self):
        text = "There were no related party transactions during fiscal year 2025."
        result = mine_structural_red_flags(text)
        assert result == {"related_party_flag": False}
