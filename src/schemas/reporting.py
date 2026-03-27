"""Pydantic schemas for Pillar 4 Phase 2: Reporting & Export endpoints."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    """Request to generate a report."""

    report_type: str
    format: str = "json"
    period_start: date | None = None
    period_end: date | None = None


class ReportResponse(BaseModel):
    """Report generation result."""

    report_id: UUID
    portfolio_id: UUID
    report_type: str
    format: str
    status: str
    data: dict | None = None

    model_config = {"from_attributes": True}


class ExportResponse(BaseModel):
    """Export metadata."""

    format: str
    content_type: str
    filename: str
    row_count: int
