"""ESG implied-temperature scoring model."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ESGTemperatureScore(TimestampMixin, Base):
    """Entity-level Paris-aligned implied temperature score."""

    __tablename__ = "esg_temperature_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    implied_temperature: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    alignment: Mapped[str] = mapped_column(String(25), nullable=False)
    scope1_emissions: Mapped[float | None] = mapped_column(Numeric(20, 2))
    scope2_emissions: Mapped[float | None] = mapped_column(Numeric(20, 2))
    scope3_emissions: Mapped[float | None] = mapped_column(Numeric(20, 2))
    emissions_trend_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    data_quality_flag: Mapped[str] = mapped_column(String(20), default="PARTIAL")

    __table_args__ = (
        Index("ix_esg_temp_entity_date", "entity_id", "as_of_date", unique=True),
    )
