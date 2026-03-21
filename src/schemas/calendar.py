"""Pydantic schemas for Corporate Actions Calendar API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CalendarEventResponse(BaseModel):
    """A calendar event for display in date-range queries."""
    event_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    security_id: uuid.UUID | None = None
    event_type: str
    event_date: date
    event_description: str | None = None
    corporate_action_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    ipo_id: uuid.UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
