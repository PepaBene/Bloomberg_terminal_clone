"""Pillar 3 Phase 3B Part 8: Legislative, regulatory, and sanctions tables.

Revision ID: 059
Revises: 058
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- legislative_bills ---
    op.create_table(
        "legislative_bills",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("bill_id", sa.String(30), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("bill_type", sa.String(20)),
        sa.Column("status", sa.String(30)),
        sa.Column("sponsor_count", sa.Integer()),
        sa.Column("passage_probability", sa.Numeric(5, 2)),
        sa.Column("affected_sectors", JSONB),
        sa.Column("affected_entity_ids", JSONB),
        sa.Column("introduced_date", sa.Date()),
        sa.Column("last_action_date", sa.Date()),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- regulatory_actions ---
    op.create_table(
        "regulatory_actions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("agency", sa.String(10)),
        sa.Column("action_type", sa.String(20)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("affected_entity_ids", JSONB),
        sa.Column("affected_sectors", JSONB),
        sa.Column("severity", sa.String(10)),
        sa.Column("financial_impact", sa.Numeric(20, 2)),
        sa.Column("action_date", sa.Date()),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- sanctions_entries ---
    op.create_table(
        "sanctions_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("program", sa.String(20)),
        sa.Column("country_code", sa.String(3)),
        sa.Column("target_name", sa.String(200)),
        sa.Column("target_type", sa.String(20)),
        sa.Column("status", sa.String(20)),
        sa.Column("effective_date", sa.Date()),
        sa.Column("description", sa.Text()),
        sa.Column("affected_sectors", JSONB),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sanctions_entries")
    op.drop_table("regulatory_actions")
    op.drop_table("legislative_bills")
