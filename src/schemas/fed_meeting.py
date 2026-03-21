"""Pydantic schemas for Fed Meeting / Central Bank Monitor API."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class FedMeetingResponse(BaseModel):
    """FOMC meeting details."""
    meeting_id: uuid.UUID
    meeting_date: date
    meeting_type: str | None = None
    rate_decision: str | None = None
    fed_funds_lower: float | None = None
    fed_funds_upper: float | None = None
    change_bps: int | None = None
    statement_text: str | None = None
    statement_url: str | None = None
    minutes_url: str | None = None
    minutes_release_date: date | None = None
    total_assets: float | None = None
    treasury_holdings: float | None = None
    mbs_holdings: float | None = None
    dot_plot_data: dict[str, Any] | None = None
    policy_id: uuid.UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
