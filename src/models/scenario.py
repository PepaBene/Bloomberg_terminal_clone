"""Pillar 2: Scenario & Sensitivity models (Spec §10).

Stores results from the E8 Scenario & Sensitivity Engine:
sensitivity tables, tornado charts, shock analyses, and break-even results.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ScenarioResult(TimestampMixin, Base):
    """Result of a scenario / sensitivity analysis."""

    __tablename__ = "scenario_results"

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=True
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(30), nullable=False)
    scenario_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Full request payload for reproducibility
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Core output (structure varies by scenario_type)
    output_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Summary scalars for quick querying
    base_case_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

    data_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")

    __table_args__ = (
        Index("idx_scenario_security_type", "security_id", "scenario_type", "calculation_date"),
    )
