"""Create entity master tables (D1).

Revision ID: 002
Revises: 001
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- entities ---
    op.create_table(
        "entities",
        sa.Column("entity_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(30), nullable=False, index=True),
        sa.Column("entity_subtype", sa.String(50)),
        # Names
        sa.Column("legal_name", sa.String(500), nullable=False, index=True),
        sa.Column("legal_name_local", sa.String(500)),
        sa.Column("short_name", sa.String(200)),
        # Status
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("status_date", sa.Date()),
        sa.Column("status_reason", sa.String(500)),
        # Incorporation
        sa.Column(
            "incorporation_country",
            sa.String(2),
            sa.ForeignKey("countries.country_code_alpha2"),
        ),
        sa.Column("incorporation_state", sa.String(50)),
        sa.Column("incorporation_date", sa.Date()),
        sa.Column("jurisdiction_type", sa.String(50)),
        # Domicile
        sa.Column(
            "domicile_country",
            sa.String(2),
            sa.ForeignKey("countries.country_code_alpha2"),
        ),
        sa.Column("domicile_address", JSONB),
        # Fiscal
        sa.Column("fiscal_year_end", sa.String(5)),
        sa.Column(
            "reporting_currency",
            sa.String(3),
            sa.ForeignKey("currencies.currency_code"),
        ),
        sa.Column("accounting_standard", sa.String(20)),
        # Classifications
        sa.Column("primary_sic", sa.String(4), sa.ForeignKey("sic_codes.sic_code")),
        sa.Column("primary_naics", sa.String(6)),
        sa.Column("gics_sector", sa.String(2)),
        sa.Column("gics_industry_group", sa.String(4)),
        sa.Column("gics_industry", sa.String(6)),
        sa.Column(
            "gics_sub_industry",
            sa.String(8),
            sa.ForeignKey("gics_classifications.sub_industry_code"),
        ),
        # Corporate hierarchy
        sa.Column(
            "ultimate_parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
        ),
        sa.Column(
            "immediate_parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
        ),
        sa.Column("ownership_percentage", sa.Numeric(5, 2)),
        sa.Column("consolidation_type", sa.String(20)),
        # Metadata
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Numeric(3, 2)),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_entities_country", "entities", ["incorporation_country"])
    op.create_index("idx_entities_gics", "entities", ["gics_sub_industry"])
    op.create_index("idx_entities_parent", "entities", ["ultimate_parent_id"])

    # --- entity_identifiers ---
    op.create_table(
        "entity_identifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("identifier_type", sa.String(30), nullable=False),
        sa.Column("identifier_value", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_entity_identifier",
        "entity_identifiers",
        ["identifier_type", "identifier_value"],
        unique=True,
    )

    # --- entity_names ---
    op.create_table(
        "entity_names",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name_type", sa.String(20), nullable=False),
        sa.Column("name_value", sa.String(500), nullable=False),
        sa.Column("effective_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("source", sa.String(50)),
    )

    # --- entity_relationships ---
    op.create_table(
        "entity_relationships",
        sa.Column("relationship_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("relationship_type", sa.String(30), nullable=False, index=True),
        sa.Column("effective_date", sa.Date()),
        sa.Column("termination_date", sa.Date()),
        sa.Column("ownership_percentage", sa.Numeric(5, 2)),
        sa.Column("relationship_details", JSONB),
        sa.Column("source", sa.String(50)),
        sa.Column("source_document", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_rel_source_type",
        "entity_relationships",
        ["source_entity_id", "relationship_type"],
    )

    # --- entities_history (PIT) ---
    op.create_table(
        "entities_history",
        sa.Column("history_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("legal_name", sa.String(500), nullable=False),
        sa.Column("short_name", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("incorporation_country", sa.String(2)),
        sa.Column("domicile_country", sa.String(2)),
        sa.Column("fiscal_year_end", sa.String(5)),
        sa.Column("reporting_currency", sa.String(3)),
        sa.Column("accounting_standard", sa.String(20)),
        sa.Column("primary_sic", sa.String(4)),
        sa.Column("gics_sub_industry", sa.String(8)),
        sa.Column("ultimate_parent_id", UUID(as_uuid=True)),
        sa.Column("immediate_parent_id", UUID(as_uuid=True)),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Numeric(3, 2)),
        # Temporal
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "idx_entity_pit",
        "entities_history",
        ["entity_id", "valid_from", "valid_to"],
    )

    # --- resolution_queue ---
    op.create_table(
        "resolution_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("source_record", JSONB, nullable=False),
        sa.Column(
            "candidate_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
        ),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False),
        sa.Column("match_method", sa.String(50)),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("reviewer", sa.String(100)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("resolution_queue")
    op.drop_table("entities_history")
    op.drop_table("entity_relationships")
    op.drop_table("entity_names")
    op.drop_table("entity_identifiers")
    op.drop_table("entities")
