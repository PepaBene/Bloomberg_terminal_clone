"""Create governance tables (lineage, catalog, revisions, connectors).

Revision ID: 005
Revises: 004
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- data_revisions ---
    op.create_table(
        "data_revisions",
        sa.Column("revision_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(20), nullable=False, index=True),
        sa.Column("record_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("revision_type", sa.String(20), nullable=False),
        sa.Column("effective_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_timestamp", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(50)),
        sa.Column("source_document", sa.String(500)),
        sa.Column("changed_fields", JSONB),
        sa.Column("change_summary", sa.Text()),
    )

    # --- lineage_records ---
    op.create_table(
        "lineage_records",
        sa.Column("lineage_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_domain", sa.String(20), nullable=False),
        sa.Column("target_table", sa.String(50), nullable=False),
        sa.Column("target_record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sources", JSONB, nullable=False),
        sa.Column("processing_timestamp", sa.DateTime(timezone=True)),
        sa.Column("processing_job_id", sa.String(100)),
        sa.Column("validation_status", sa.String(10)),
        sa.Column("validation_details", JSONB),
    )

    # --- data_catalog ---
    op.create_table(
        "data_catalog",
        sa.Column("entry_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(20), nullable=False),
        sa.Column("dataset_name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("business_definition", sa.Text()),
        sa.Column("schema_version", sa.String(20)),
        sa.Column("fields", JSONB),
        sa.Column("steward", sa.String(100)),
        sa.Column("team", sa.String(100)),
        sa.Column("sensitivity", sa.String(20)),
        sa.Column("pii_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quality_score", sa.Numeric(5, 2)),
        sa.Column("update_frequency", sa.String(20)),
        sa.Column("access_pattern", sa.Text()),
    )

    # --- source_connectors ---
    op.create_table(
        "source_connectors",
        sa.Column("connector_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("connector_type", sa.String(20), nullable=False),
        sa.Column("endpoint", sa.String(500)),
        sa.Column("authentication", JSONB),
        sa.Column("schedule", sa.String(50)),
        sa.Column("data_domain", sa.String(20)),
        sa.Column("data_format", sa.String(10)),
        sa.Column("parser_class", sa.String(200)),
        sa.Column("validation_rules", JSONB),
        sa.Column("expected_frequency", sa.String(20)),
        sa.Column("alert_on_delay", sa.String(20)),
        sa.Column("max_processing_time", sa.String(20)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_table("source_connectors")
    op.drop_table("data_catalog")
    op.drop_table("lineage_records")
    op.drop_table("data_revisions")
