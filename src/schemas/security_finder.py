"""Pydantic schemas for security finder."""

import uuid

from pydantic import BaseModel


class SecurityFinderResult(BaseModel):
    """Single result from security search."""
    security_id: uuid.UUID
    name: str
    short_name: str | None = None
    security_type: str
    asset_class: str | None = None
    status: str | None = None
    relevance_score: float = 0.0


class SecurityFinderResponse(BaseModel):
    """Security finder response."""
    query: str
    total_results: int
    results: list[SecurityFinderResult] = []


class SecuritySuggestion(BaseModel):
    """Autocomplete suggestion."""
    security_id: uuid.UUID
    display: str
    security_type: str
