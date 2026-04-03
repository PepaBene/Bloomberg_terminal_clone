"""Pydantic schemas for Executive/Director API."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ExecutiveRoleResponse(BaseModel):
    """Role held by an executive."""
    role_id: uuid.UUID
    entity_id: uuid.UUID
    title: str
    role_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_independent: bool | None = None

    model_config = {"from_attributes": True}


class ExecutiveResponse(BaseModel):
    """Executive with roles."""
    executive_id: uuid.UUID
    person_name: str
    bio_text: str | None = None
    education: dict | list | None = None
    age: int | None = None
    total_compensation: Decimal | None = None
    base_salary: Decimal | None = None
    bonus: Decimal | None = None
    stock_awards: Decimal | None = None
    option_awards: Decimal | None = None
    other_compensation: Decimal | None = None
    roles: list[ExecutiveRoleResponse] = []
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
