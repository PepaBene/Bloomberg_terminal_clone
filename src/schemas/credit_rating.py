"""Pydantic schemas for Credit Rating History API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CreditRatingEventResponse(BaseModel):
    """A single credit rating event."""
    event_id: uuid.UUID
    entity_id: uuid.UUID
    agency: str
    rating_type: str | None = None
    new_rating: str | None = None
    old_rating: str | None = None
    direction: str | None = None
    outlook: str | None = None
    event_date: date
    effective_date: date | None = None
    source_type: str | None = None
    source_url: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
