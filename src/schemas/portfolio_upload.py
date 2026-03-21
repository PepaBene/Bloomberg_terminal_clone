"""Pydantic schemas for portfolio upload."""

import uuid

from pydantic import BaseModel


class ParsedHoldingRow(BaseModel):
    """Single row from a parsed portfolio file."""
    row_number: int
    identifier: str | None = None
    name: str | None = None
    quantity: float | None = None
    weight: float | None = None
    mapping_status: str = "NOT_FOUND"
    matched_security_id: uuid.UUID | None = None


class UploadResultResponse(BaseModel):
    """Portfolio upload result."""

    model_config = {"from_attributes": True}

    upload_id: uuid.UUID
    file_name: str
    file_format: str
    status: str
    total_rows: int | None = None
    matched_rows: int | None = None
    unmatched_rows: int | None = None
    holdings: list[ParsedHoldingRow] = []
