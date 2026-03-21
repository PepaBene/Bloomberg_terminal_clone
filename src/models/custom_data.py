"""Custom data environment models (Pillar 2 Supplement – Part 6)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CustomFieldDefinition(TimestampMixin, Base):
    """User-defined computed field definition."""

    __tablename__ = "custom_field_definitions"

    field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="NUMERIC")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="PRIVATE")
    created_by: Mapped[str | None] = mapped_column(String(100))
    depends_on: Mapped[dict | None] = mapped_column(JSONB)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text)


class CustomFieldValue(TimestampMixin, Base):
    """Computed value of a custom field for a specific security/entity."""

    __tablename__ = "custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custom_field_definitions.field_id"),
        nullable=False, index=True,
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )
    value_numeric: Mapped[float | None] = mapped_column(Numeric(20, 6))
    value_string: Mapped[str | None] = mapped_column(String(500))
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    period: Mapped[str | None] = mapped_column(String(20))
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_cfv_field_security", "field_id", "security_id"),
        Index("idx_cfv_field_entity", "field_id", "entity_id"),
    )
