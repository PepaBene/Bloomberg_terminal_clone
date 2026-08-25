"""PII redaction: hash insider/individual names before they hit telemetry.

``ai_call_log`` persists prompt/response text for audit -- if a prompt or
answer names a specific insider (e.g. discussing a Form 4 transaction),
that name shouldn't sit in plaintext in a log table. This replaces each
occurrence of a known name with a stable, non-reversible short hash so the
same name always redacts to the same token (useful for spotting repeated
mentions across log rows without storing the name itself).

Pure, no DB/LLM call -- callers supply the names to redact (e.g. the
``insider_name`` values already resolved for the entities/subjects a given
request touched), this module doesn't discover names on its own.
"""
from __future__ import annotations

import hashlib
import re

_HASH_LENGTH = 10


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:_HASH_LENGTH]


def redact_names(text: str, names: list[str]) -> str:
    """Replace whole-word, case-insensitive occurrences of each name.

    Longest names are substituted first so a full name ("Jane A. Smith")
    doesn't get partially clobbered by a shorter one ("Jane") matching
    inside it first.
    """
    if not text or not names:
        return text
    ordered = sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True)
    for name in ordered:
        token = f"[REDACTED:{_short_hash(name)}]"
        text = re.sub(rf"\b{re.escape(name)}\b", token, text, flags=re.IGNORECASE)
    return text
