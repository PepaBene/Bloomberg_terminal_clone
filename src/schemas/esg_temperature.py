"""Pydantic schemas for ESG temperature scores."""

import uuid
from datetime import date

from pydantic import BaseModel


class ESGTemperatureResponse(BaseModel):
    """Entity ESG implied-temperature score."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    entity_id: uuid.UUID
    as_of_date: date
    implied_temperature: float
    alignment: str
    scope1_emissions: float | None = None
    scope2_emissions: float | None = None
    scope3_emissions: float | None = None
    emissions_trend_pct: float | None = None
    data_quality_flag: str = "PARTIAL"
