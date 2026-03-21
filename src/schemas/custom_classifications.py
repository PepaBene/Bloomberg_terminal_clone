"""Pydantic schemas for custom classifications."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ClassificationMemberResponse(BaseModel):
    """A member entity within a classification."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    classification_id: uuid.UUID
    entity_id: uuid.UUID
    added_at: datetime
    tags: dict | None = None


class ClassificationResponse(BaseModel):
    """Custom classification with nested members."""

    model_config = {"from_attributes": True}

    classification_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    visibility: str = "PRIVATE"
    members: list[ClassificationMemberResponse] = []


class ClassificationCreateRequest(BaseModel):
    """Request body to create a custom classification."""

    name: str
    description: str | None = None
    visibility: str = "PRIVATE"


class ClassificationMemberRequest(BaseModel):
    """Request body to add a member to a classification."""

    entity_id: uuid.UUID
    tags: dict | None = None
