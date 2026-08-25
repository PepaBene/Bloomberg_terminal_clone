"""Response guardrails: citation enforcement, date consistency, PII
redaction, and per-user cost budgets.

Public surface:
    from src.ai.guardrails import find_uncited_numeric_claims, verify_citations
    from src.ai.guardrails import find_future_dated_claims
    from src.ai.guardrails import redact_names
    from src.ai.guardrails import check_budget, BudgetExceededError
"""
from src.ai.guardrails.budget import (
    DEFAULT_DAILY_TOKEN_BUDGET,
    BudgetExceededError,
    check_budget,
)
from src.ai.guardrails.citations import (
    CitationIssue,
    check_response,
    extract_cited_sentences,
    find_uncited_numeric_claims,
    verify_citations,
)
from src.ai.guardrails.dates import DateIssue, find_future_dated_claims
from src.ai.guardrails.redaction import redact_names

__all__ = [
    "CitationIssue",
    "find_uncited_numeric_claims",
    "extract_cited_sentences",
    "verify_citations",
    "check_response",
    "DateIssue",
    "find_future_dated_claims",
    "redact_names",
    "check_budget",
    "BudgetExceededError",
    "DEFAULT_DAILY_TOKEN_BUDGET",
]
