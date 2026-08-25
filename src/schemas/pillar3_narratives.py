"""Pydantic schemas for §4.7's commodity/insider narrative endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class CommodityNarrativeResponse(BaseModel):
    commodity_code: str
    as_of_date: date
    narrative: str
    price_summary: dict | None = None
    news_article_ids: list | None = None
    model: str | None = None

    model_config = {"from_attributes": True}


class InsiderNarrativeResponse(BaseModel):
    entity_id: uuid.UUID
    as_of_date: date
    narrative: str
    signal_summary: dict | None = None
    congressional_summary: dict | None = None
    model: str | None = None

    model_config = {"from_attributes": True}
