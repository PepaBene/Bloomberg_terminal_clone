"""Unit tests for src/ai/guardrails/*.

citations/dates/redaction are pure. budget.check_budget is exercised
against the SQLite test engine (record_call already writes real
ai_call_log rows there, per test_ai_core.py's test_record_call_writes_row).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.ai.guardrails.budget import (
    DEFAULT_DAILY_TOKEN_BUDGET,
    BudgetExceededError,
    check_budget,
)
from src.ai.guardrails.citations import (
    check_response,
    extract_cited_sentences,
    find_uncited_numeric_claims,
    verify_citations,
)
from src.ai.guardrails.dates import find_future_dated_claims
from src.ai.guardrails.redaction import redact_names
from src.ai.models import Tier
from src.ai.telemetry import AICallRecord, Usage, record_call


# --------------------------------------------------------------------------- #
# citations
# --------------------------------------------------------------------------- #
def test_find_uncited_numeric_claims_flags_missing_citation():
    text = "Revenue grew 12% this quarter. The company also expanded headcount."
    issues = find_uncited_numeric_claims(text)
    assert len(issues) == 1
    assert "12%" in issues[0].sentence
    assert issues[0].reason == "missing_citation"


def test_find_uncited_numeric_claims_passes_when_cited():
    text = "Revenue grew 12% this quarter [doc1]."
    assert find_uncited_numeric_claims(text) == []


def test_find_uncited_numeric_claims_ignores_sentences_without_numbers():
    text = "The company continues to grow steadily. Management remains confident."
    assert find_uncited_numeric_claims(text) == []


def test_extract_cited_sentences():
    text = "Revenue grew 12% [doc1]. Margins held flat. Costs rose [doc2][doc3]."
    result = extract_cited_sentences(text)
    assert len(result) == 2
    assert result[0] == ("Revenue grew 12% [doc1].", ["doc1"])
    assert result[1][1] == ["doc2", "doc3"]


def test_verify_citations_supported():
    text = "Revenue grew 12% to $4.2 billion [doc1]."
    citation_map = {"doc1": "The company's revenue grew 12% to $4.2 billion in Q3."}
    assert verify_citations(text, citation_map) == []


def test_verify_citations_unsupported():
    text = "Revenue grew 90% due to a merger [doc1]."
    citation_map = {"doc1": "The weather was sunny and pleasant today."}
    issues = verify_citations(text, citation_map)
    assert len(issues) == 1
    assert issues[0].reason == "unsupported_citation"
    assert issues[0].markers == ["doc1"]


def test_verify_citations_missing_marker_in_map_is_unsupported():
    text = "Revenue grew 12% [doc_not_in_map]."
    issues = verify_citations(text, {})
    assert len(issues) == 1


def test_verify_citations_passes_if_any_of_multiple_markers_supports():
    text = "Revenue grew 12% to $4.2 billion [doc1][doc2]."
    citation_map = {
        "doc1": "irrelevant filler text about something else entirely",
        "doc2": "revenue grew 12% to $4.2 billion in the third quarter",
    }
    assert verify_citations(text, citation_map) == []


def test_check_response_combines_both_checks():
    text = "Revenue grew 12% with no citation. Costs rose 5% [doc1]."
    issues = check_response(text, citation_map={"doc1": "unrelated text"})
    reasons = {i.reason for i in issues}
    assert reasons == {"missing_citation", "unsupported_citation"}


# --------------------------------------------------------------------------- #
# dates
# --------------------------------------------------------------------------- #
def test_find_future_dated_claims_iso_date():
    issues = find_future_dated_claims(
        "The deal is expected to close on 2027-03-15.", as_of=date(2026, 1, 1)
    )
    assert len(issues) == 1
    assert issues[0].found_date == "2027-03-15"


def test_find_future_dated_claims_full_month_date():
    issues = find_future_dated_claims(
        "Guidance points to a recovery by March 15, 2027.", as_of=date(2026, 1, 1)
    )
    assert len(issues) == 1
    assert issues[0].found_date == "2027-03-15"


def test_find_future_dated_claims_bare_year():
    issues = find_future_dated_claims(
        "Analysts expect margin recovery by 2028.", as_of=date(2026, 1, 1)
    )
    assert len(issues) == 1
    assert issues[0].found_date == "2028"


def test_find_future_dated_claims_past_and_present_are_fine():
    text = "The company reported FY2024 results on 2025-02-10. Current guidance for 2026 remains unchanged."
    assert find_future_dated_claims(text, as_of=date(2026, 6, 1)) == []


def test_find_future_dated_claims_one_issue_per_sentence():
    issues = find_future_dated_claims(
        "Expected close 2027-03-15 or possibly 2028.", as_of=date(2026, 1, 1)
    )
    assert len(issues) == 1  # not double-flagged for the ISO date + bare year


# --------------------------------------------------------------------------- #
# redaction
# --------------------------------------------------------------------------- #
def test_redact_names_replaces_whole_word_case_insensitive():
    text = "Jane Smith sold 10,000 shares. jane smith also filed a Form 4."
    redacted = redact_names(text, ["Jane Smith"])
    assert "Jane Smith" not in redacted
    assert "jane smith" not in redacted.lower().replace("[redacted", "")
    assert redacted.count("[REDACTED:") == 2


def test_redact_names_same_name_same_hash():
    r1 = redact_names("Jane Smith did X.", ["Jane Smith"])
    r2 = redact_names("Later, Jane Smith did Y.", ["Jane Smith"])
    token1 = r1.split("did")[0].strip()
    token2 = r2.split("Later,")[1].split("did")[0].strip()
    assert token1 == token2


def test_redact_names_longest_first_avoids_partial_clobber():
    text = "Jane Smith and Jane Doe both sold shares."
    redacted = redact_names(text, ["Jane", "Jane Smith", "Jane Doe"])
    assert "Jane Smith" not in redacted
    assert "Jane Doe" not in redacted
    assert redacted.count("[REDACTED:") == 2


def test_redact_names_empty_inputs():
    assert redact_names("", ["Jane"]) == ""
    assert redact_names("some text", []) == "some text"


# --------------------------------------------------------------------------- #
# budget
# --------------------------------------------------------------------------- #
async def test_check_budget_noop_for_light_tier(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # No rows at all, but light tier should never even look — pass an
    # impossible limit=0 to prove it's not checking usage.
    await check_budget("user-1", tier=Tier.LIGHT, limit=0, session_factory=factory)


async def test_check_budget_noop_without_user_id(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await check_budget(None, tier=Tier.SYNTHESIS, limit=0, session_factory=factory)


async def test_check_budget_passes_under_limit(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    rec = AICallRecord(
        feature="test", model="claude-sonnet-5",
        usage=Usage(input_tokens=1000, output_tokens=500), user_id="user-under",
    )
    await record_call(rec, session_factory=factory)
    await check_budget("user-under", tier=Tier.SYNTHESIS, limit=1_000_000, session_factory=factory)


async def test_check_budget_raises_over_limit(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    rec = AICallRecord(
        feature="test", model="claude-sonnet-5",
        usage=Usage(input_tokens=800, output_tokens=300), user_id="user-over",
    )
    await record_call(rec, session_factory=factory)
    with pytest.raises(BudgetExceededError) as exc_info:
        await check_budget("user-over", tier=Tier.SYNTHESIS, limit=1000, session_factory=factory)
    assert exc_info.value.used >= 1000
    assert exc_info.value.limit == 1000


def test_default_daily_token_budget_is_ten_million():
    assert DEFAULT_DAILY_TOKEN_BUDGET == 10_000_000
