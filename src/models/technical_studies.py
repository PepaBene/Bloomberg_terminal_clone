"""Technical study / indicator value model."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class TechnicalStudyValue(TimestampMixin, Base):
    """Pre-computed technical indicator value for a security on a given date."""

    __tablename__ = "technical_study_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False
    )
    study_date: Mapped[date] = mapped_column(Date, nullable=False)
    indicator: Mapped[str] = mapped_column(String(25), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    category: Mapped[str | None] = mapped_column(String(15))

    __table_args__ = (
        Index("ix_tsv_security_date_indicator", "security_id", "study_date", "indicator", unique=True),
    )
