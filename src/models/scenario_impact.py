"""Pillar 3 Phase 4C: Scenario company impact model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ScenarioCompanyImpact(Base):
    """Impact of a macro scenario on a specific company."""

    __tablename__ = "scenario_company_impacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("macro_scenarios.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    base_eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    scenario_eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    eps_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    margin_impact_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rating_implication: Mapped[str | None] = mapped_column(String(15))
    price_target_scenario: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
