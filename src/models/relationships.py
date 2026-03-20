"""Domain 10: Business Relationships models (Spec Section 12)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class BusinessRelationship(TimestampMixin, Base):
    """Business relationships between entities (Spec 12.2)."""

    __tablename__ = "business_relationships"

    # Primary key
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Entity references
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )

    # Relationship classification
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    direction: Mapped[str | None] = mapped_column(String(20))

    # Financial metrics
    revenue_percentage: Mapped[float | None] = mapped_column(Numeric(6, 4))
    cost_percentage: Mapped[float | None] = mapped_column(Numeric(6, 4))
    contract_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    contract_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )

    # Contract dates
    contract_start_date: Mapped[date | None] = mapped_column(Date)
    contract_end_date: Mapped[date | None] = mapped_column(Date)

    # Risk and confidence
    is_single_source: Mapped[bool | None] = mapped_column(Boolean)
    materiality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Extraction provenance
    extraction_method: Mapped[str | None] = mapped_column(String(30))
    source_document: Mapped[str | None] = mapped_column(String(500))
    source_text: Mapped[str | None] = mapped_column(Text)

    # Temporal validity
    effective_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Flexible metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_brel_source_type", "source_entity_id", "relationship_type"),
        Index("idx_brel_target_type", "target_entity_id", "relationship_type"),
    )


class RelationshipHistory(Base):
    """Change history for business relationships (Spec 12.3)."""

    __tablename__ = "relationship_history"

    # Primary key
    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Link to parent relationship
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_relationships.relationship_id"),
        nullable=False,
        index=True,
    )

    # Change details
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    change_date: Mapped[date | None] = mapped_column(Date)

    # Metric deltas
    previous_revenue_percentage: Mapped[float | None] = mapped_column(Numeric(6, 4))
    new_revenue_percentage: Mapped[float | None] = mapped_column(Numeric(6, 4))
    previous_materiality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    new_materiality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Flexible change info
    change_details: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str | None] = mapped_column(String(50))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
