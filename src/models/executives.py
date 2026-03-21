"""Pillar 1 Supplement: Executive/Director Database models (Part 4)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Executive(TimestampMixin, Base):
    """Individual executive/director."""

    __tablename__ = "executives"

    executive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    person_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    bio_text: Mapped[str | None] = mapped_column(Text)
    education: Mapped[dict | None] = mapped_column(JSONB)
    age: Mapped[int | None] = mapped_column(Integer)
    total_compensation: Mapped[float | None] = mapped_column(Numeric(20, 2))
    base_salary: Mapped[float | None] = mapped_column(Numeric(20, 2))
    bonus: Mapped[float | None] = mapped_column(Numeric(20, 2))
    stock_awards: Mapped[float | None] = mapped_column(Numeric(20, 2))
    option_awards: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_compensation: Mapped[float | None] = mapped_column(Numeric(20, 2))

    roles = relationship("ExecutiveRole", back_populates="executive", lazy="selectin")


class ExecutiveRole(TimestampMixin, Base):
    """Role held by an executive at a specific entity."""

    __tablename__ = "executive_roles"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    executive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executives.executive_id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    role_type: Mapped[str | None] = mapped_column(String(10))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_independent: Mapped[bool | None] = mapped_column(Boolean)

    executive = relationship("Executive", back_populates="roles")

    __table_args__ = (
        Index("idx_role_entity_type", "entity_id", "role_type"),
    )
