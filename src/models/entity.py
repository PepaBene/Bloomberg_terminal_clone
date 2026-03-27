"""Domain 1: Entity Master models (Spec Section 3)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Entity(TimestampMixin, Base):
    """Canonical registry of all legal entities (Spec 3.3)."""

    __tablename__ = "entities"

    # Primary identification
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_subtype: Mapped[str | None] = mapped_column(String(50))

    # Names
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    legal_name_local: Mapped[str | None] = mapped_column(String(500))
    short_name: Mapped[str | None] = mapped_column(String(200))

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status_date: Mapped[date | None] = mapped_column(Date)
    status_reason: Mapped[str | None] = mapped_column(String(500))

    # Incorporation
    incorporation_country: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.country_code_alpha2")
    )
    incorporation_state: Mapped[str | None] = mapped_column(String(50))
    incorporation_date: Mapped[date | None] = mapped_column(Date)
    jurisdiction_type: Mapped[str | None] = mapped_column(String(50))

    # Domicile
    domicile_country: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.country_code_alpha2")
    )
    domicile_address: Mapped[dict | None] = mapped_column(JSONB)

    # Fiscal information
    fiscal_year_end: Mapped[str | None] = mapped_column(String(5))  # "MM-DD"
    reporting_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    accounting_standard: Mapped[str | None] = mapped_column(String(20))

    # Classification links
    primary_sic: Mapped[str | None] = mapped_column(
        String(4), ForeignKey("sic_codes.sic_code")
    )
    primary_naics: Mapped[str | None] = mapped_column(String(6))
    gics_sector: Mapped[str | None] = mapped_column(String(2))
    gics_industry_group: Mapped[str | None] = mapped_column(String(4))
    gics_industry: Mapped[str | None] = mapped_column(String(6))
    gics_sub_industry: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("gics_classifications.sub_industry_code")
    )

    # Corporate hierarchy
    ultimate_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    immediate_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    consolidation_type: Mapped[str | None] = mapped_column(String(20))

    # D11 FI Supplement: Issuer linkage
    is_financing_subsidiary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    financing_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )

    # Metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Relationships
    identifiers = relationship("EntityIdentifier", back_populates="entity", lazy="selectin")
    names = relationship("EntityName", back_populates="entity", lazy="selectin")

    __table_args__ = (
        Index("idx_entities_country", "incorporation_country"),
        Index("idx_entities_gics", "gics_sub_industry"),
        Index("idx_entities_parent", "ultimate_parent_id"),
    )


class EntityIdentifier(Base):
    """External identifiers for entities — all 11 types (Spec 3.3)."""

    __tablename__ = "entity_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity = relationship("Entity", back_populates="identifiers")

    __table_args__ = (
        Index("uq_entity_identifier", "identifier_type", "identifier_value", unique=True),
    )


class EntityName(Base):
    """Historical and alternative names (Spec 3.3 previous_names + aliases)."""

    __tablename__ = "entity_names"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    name_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name_value: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(50))

    entity = relationship("Entity", back_populates="names")


class EntityRelationship(Base):
    """Relationships between entities (Spec 3.4)."""

    __tablename__ = "entity_relationships"

    relationship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    relationship_details: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str | None] = mapped_column(String(50))
    source_document: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_rel_source_type", "source_entity_id", "relationship_type"),
    )


class EntityHistory(Base):
    """Point-in-time history for entities (Spec 14.2)."""

    __tablename__ = "entities_history"

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Snapshot of entity fields
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    incorporation_country: Mapped[str | None] = mapped_column(String(2))
    domicile_country: Mapped[str | None] = mapped_column(String(2))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(5))
    reporting_currency: Mapped[str | None] = mapped_column(String(3))
    accounting_standard: Mapped[str | None] = mapped_column(String(20))
    primary_sic: Mapped[str | None] = mapped_column(String(4))
    gics_sub_industry: Mapped[str | None] = mapped_column(String(8))
    ultimate_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    immediate_parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Temporal fields
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_entity_pit", "entity_id", "valid_from", "valid_to"),
    )


class ResolutionQueue(Base):
    """Entity resolution review queue (Spec 3.5)."""

    __tablename__ = "resolution_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record: Mapped[dict] = mapped_column(JSONB, nullable=False)
    candidate_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    match_method: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(100))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
