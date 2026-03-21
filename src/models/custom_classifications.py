"""Custom user-defined classification models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CustomClassification(TimestampMixin, Base):
    """User-created classification / watchlist / portfolio grouping."""

    __tablename__ = "custom_classifications"

    classification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(10), default="PRIVATE")

    members: Mapped[list["ClassificationMember"]] = relationship(
        back_populates="classification", lazy="selectin"
    )


class ClassificationMember(Base):
    """An entity assigned to a custom classification."""

    __tablename__ = "classification_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    classification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_classifications.classification_id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tags: Mapped[dict | None] = mapped_column(JSONB)

    classification: Mapped["CustomClassification"] = relationship(
        back_populates="members"
    )

    __table_args__ = (
        Index("ix_cm_classification_entity", "classification_id", "entity_id", unique=True),
    )
