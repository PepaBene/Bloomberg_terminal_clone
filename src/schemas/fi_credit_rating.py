"""Pydantic schemas for Fixed Income Credit Rating endpoints (D11 FI Supplement P5)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CreditRatingEventResponse(BaseModel):
    """A credit rating event with FI supplement fields."""

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
    # D11 FI Supplement fields
    new_rating_numeric: int | None = None
    old_rating_numeric: int | None = None
    notches_changed: int | None = None
    is_fallen_angel: bool = False
    is_rising_star: bool = False
    entity_stock_price_at_event: float | None = None
    bond_spread_at_event: float | None = None
    watch_status: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CurrentCreditRatingResponse(BaseModel):
    """Current credit rating snapshot per entity per agency."""

    id: uuid.UUID
    entity_id: uuid.UUID
    agency: str
    rating_type: str | None = None
    current_rating: str
    current_rating_numeric: int | None = None
    outlook: str | None = None
    watch_status: str | None = None
    last_action_date: date | None = None
    last_action_type: str | None = None
    is_investment_grade: bool | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FallenAngelResponse(BaseModel):
    """Fallen angel event summary."""

    event_id: uuid.UUID
    entity_id: uuid.UUID
    agency: str
    old_rating: str | None = None
    new_rating: str | None = None
    event_date: date
    notches_changed: int | None = None

    model_config = {"from_attributes": True}


class RisingStarResponse(BaseModel):
    """Rising star event summary."""

    event_id: uuid.UUID
    entity_id: uuid.UUID
    agency: str
    old_rating: str | None = None
    new_rating: str | None = None
    event_date: date
    notches_changed: int | None = None

    model_config = {"from_attributes": True}


class RatingMigrationMatrixResponse(BaseModel):
    """Rating transition matrix."""

    matrix: dict[str, dict[str, int]]
    total_transitions: int
    start_date: date | None = None
    end_date: date | None = None


class RatingActionResponse(BaseModel):
    """A recent rating action summary."""

    event_id: uuid.UUID
    entity_id: uuid.UUID
    agency: str
    direction: str | None = None
    new_rating: str | None = None
    old_rating: str | None = None
    event_date: date
    is_fallen_angel: bool = False
    is_rising_star: bool = False

    model_config = {"from_attributes": True}
