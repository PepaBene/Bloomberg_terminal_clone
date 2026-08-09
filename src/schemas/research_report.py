"""Pydantic schemas for Layer 2 on-demand Deep Research (§4.6)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class DeepResearchRequest(BaseModel):
    subject_type: str = "FREE_TEXT"  # ENTITY|SECTOR|MACRO|FREE_TEXT
    subject_id: str | None = None
    free_text: str | None = None
    focus: str | None = None

    @model_validator(mode="after")
    def _require_subject_id_or_free_text(self) -> "DeepResearchRequest":
        if not self.subject_id and not self.free_text:
            raise ValueError("either subject_id or free_text is required")
        return self


class ResearchSectionResponse(BaseModel):
    title: str
    content: str
    citations: list[str] = []


class ResearchReportResponse(BaseModel):
    id: uuid.UUID
    subject_type: str
    subject_id: str | None = None
    subject_label: str
    focus: str | None = None
    sections: list[ResearchSectionResponse] = []
    sources: list[str] = []
    confidence: float | None = None
    model: str | None = None
    status: str
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_report(cls, report) -> "ResearchReportResponse":
        """Build from a ``ResearchReport`` ORM row. Not plain
        ``model_validate(report, from_attributes=True)`` -- ``sections``/
        ``sources`` are NULL on the row until the run completes
        (PENDING/RUNNING/FAILED), and mutating the live ORM object to
        paper over that (e.g. a ``model_validator`` doing
        ``setattr(report, "sections", [])``) would risk persisting that
        change back to the row -- so the None->[] normalization happens
        here, on plain field values, never touching the ORM object.
        """
        return cls(
            id=report.id, subject_type=report.subject_type, subject_id=report.subject_id,
            subject_label=report.subject_label, focus=report.focus,
            sections=report.sections or [], sources=report.sources or [],
            confidence=float(report.confidence) if report.confidence is not None else None,
            model=report.model, status=report.status, error=report.error,
            created_at=report.created_at, completed_at=report.completed_at,
        )
