"""Pydantic schemas for custom data environment."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateCustomFieldRequest(BaseModel):
    """Request to create a custom computed field."""
    name: str
    description: str | None = None
    expression: str
    field_type: str = "NUMERIC"
    scope: str = "PRIVATE"


class ValidateExpressionRequest(BaseModel):
    """Request to validate an expression."""
    expression: str


class ValidateExpressionResponse(BaseModel):
    """Response from expression validation."""
    is_valid: bool
    error: str | None = None
    dependencies: list[str] = []


class CustomFieldDefinitionResponse(BaseModel):
    """Response for a custom field definition."""
    field_id: uuid.UUID
    name: str
    description: str | None = None
    expression: str
    field_type: str
    scope: str
    created_by: str | None = None
    depends_on: list[str] | None = None
    is_valid: bool = True
    validation_error: str | None = None

    model_config = {"from_attributes": True}


class CustomFieldValueResponse(BaseModel):
    """Response for a computed custom field value."""
    field_id: uuid.UUID
    security_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
    value_numeric: float | None = None
    value_string: str | None = None
    value_boolean: bool | None = None
    period: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}
