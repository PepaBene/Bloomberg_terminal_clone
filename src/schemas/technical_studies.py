"""Pydantic schemas for technical study values."""

import uuid
from datetime import date

from pydantic import BaseModel


class TechnicalStudyResponse(BaseModel):
    """Single technical indicator reading."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    security_id: uuid.UUID
    study_date: date
    indicator: str
    value: float
    category: str | None = None
