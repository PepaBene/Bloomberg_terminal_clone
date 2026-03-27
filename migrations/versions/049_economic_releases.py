"""Pillar 3 Phase 2: Economic calendar / releases.

Revision ID: 049
Revises: 048
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- economic_releases ---
    op.create_table(
        "economic_releases",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("release_type", sa.String(40), nullable=False),
        sa.Column("release_category", sa.String(30), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("release_time", sa.String(10)),
        sa.Column("country_code", sa.String(3), server_default=sa.text("'US'")),
        sa.Column("period_label", sa.String(30)),
        sa.Column("consensus_value", sa.Numeric(20, 4)),
        sa.Column("prior_value", sa.Numeric(20, 4)),
        sa.Column("actual_value", sa.Numeric(20, 4)),
        sa.Column("surprise_value", sa.Numeric(20, 4)),
        sa.Column("surprise_magnitude", sa.Numeric(8, 4)),
        sa.Column("sector_sensitivity", JSONB),
        sa.Column("historical_reactions", JSONB),
        sa.Column("affected_entity_ids", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("importance", sa.String(10)),
        sa.Column("source", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_econ_release_date", "economic_releases", ["release_date"])
    op.create_index(
        "idx_econ_release_date_type",
        "economic_releases",
        ["release_date", "release_type"],
    )
    op.create_index(
        "idx_econ_category_date",
        "economic_releases",
        ["release_category", "release_date"],
    )


def downgrade() -> None:
    op.drop_table("economic_releases")
