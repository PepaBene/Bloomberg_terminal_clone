"""Pillar 3 Phase 3C: Alert expansion models."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class FIAlertConfig(TimestampMixin, Base):
    """User-configurable fixed-income alert configuration."""

    __tablename__ = "fi_alert_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    entity_scope: Mapped[dict | None] = mapped_column(JSONB)
