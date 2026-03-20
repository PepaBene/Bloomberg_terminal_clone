"""Data Governance models: Lineage, Catalog, Revisions, Connectors (Spec Sections 14, 15, 18)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DataRevision(Base):
    """Revision tracking for point-in-time data (Spec 14.3)."""

    __tablename__ = "data_revisions"

    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision_type: Mapped[str] = mapped_column(String(20), nullable=False)

    effective_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[str | None] = mapped_column(String(50))
    source_document: Mapped[str | None] = mapped_column(String(500))

    changed_fields: Mapped[dict | None] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text)


class LineageRecord(Base):
    """Data lineage tracking (Spec 18.2)."""

    __tablename__ = "lineage_records"

    lineage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_domain: Mapped[str] = mapped_column(String(20), nullable=False)
    target_table: Mapped[str] = mapped_column(String(50), nullable=False)
    target_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    sources: Mapped[dict] = mapped_column(JSONB, nullable=False)

    processing_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_job_id: Mapped[str | None] = mapped_column(String(100))

    validation_status: Mapped[str | None] = mapped_column(String(10))
    validation_details: Mapped[dict | None] = mapped_column(JSONB)


class DataCatalogEntry(Base):
    """Data catalog entries (Spec 18.3)."""

    __tablename__ = "data_catalog"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(20), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    description: Mapped[str | None] = mapped_column(Text)
    business_definition: Mapped[str | None] = mapped_column(Text)

    schema_version: Mapped[str | None] = mapped_column(String(20))
    fields: Mapped[dict | None] = mapped_column(JSONB)

    steward: Mapped[str | None] = mapped_column(String(100))
    team: Mapped[str | None] = mapped_column(String(100))

    sensitivity: Mapped[str | None] = mapped_column(String(20))
    pii_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    quality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    update_frequency: Mapped[str | None] = mapped_column(String(20))
    access_pattern: Mapped[str | None] = mapped_column(Text)


class SourceConnector(Base):
    """Source connector configuration (Spec 15.3)."""

    __tablename__ = "source_connectors"

    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(20), nullable=False)

    endpoint: Mapped[str | None] = mapped_column(String(500))
    authentication: Mapped[dict | None] = mapped_column(JSONB)

    schedule: Mapped[str | None] = mapped_column(String(50))

    data_domain: Mapped[str | None] = mapped_column(String(20))
    data_format: Mapped[str | None] = mapped_column(String(10))

    parser_class: Mapped[str | None] = mapped_column(String(200))
    validation_rules: Mapped[dict | None] = mapped_column(JSONB)

    expected_frequency: Mapped[str | None] = mapped_column(String(20))
    alert_on_delay: Mapped[str | None] = mapped_column(String(20))
    max_processing_time: Mapped[str | None] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
