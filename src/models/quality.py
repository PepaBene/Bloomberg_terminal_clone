"""Data Quality Framework models (Spec Section 13)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DataQualityScore(Base):
    """Domain-level quality scores (Spec 13.3)."""

    __tablename__ = "data_quality_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Overall score 0-100
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # Dimension scores
    accuracy_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    timeliness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    consistency_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Issue counts
    issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DataQualityIssue(Base):
    """Individual quality issues detected (Spec 13.3)."""

    __tablename__ = "data_quality_issues"

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    issue_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    field_name: Mapped[str | None] = mapped_column(String(100))
    issue_description: Mapped[str | None] = mapped_column(Text)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
