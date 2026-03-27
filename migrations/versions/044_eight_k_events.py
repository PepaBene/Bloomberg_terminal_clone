"""Pillar 3 Phase 1: 8-K event tracking.

Revision ID: 044
Revises: 043
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eight_k_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("item_number", sa.String(10), nullable=False),
        sa.Column("item_description", sa.String(200)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("raw_text", sa.Text()),
        sa.Column("monetary_figures", JSONB),
        sa.Column("key_dates", JSONB),
        sa.Column("key_people", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("materiality", sa.String(10)),
        sa.Column("filing_accession_number", sa.String(25)),
        sa.Column("filing_url", sa.String(500)),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_8k_entity_date", "eight_k_events", ["entity_id", "filing_date"])
    op.create_index("idx_8k_priority_date", "eight_k_events", ["priority", "filing_date"])
    op.create_index("idx_8k_item_date", "eight_k_events", ["item_number", "filing_date"])


def downgrade() -> None:
    op.drop_table("eight_k_events")
