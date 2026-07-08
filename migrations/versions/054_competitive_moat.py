"""Pillar 3 Phase 3A Part 1: Competitive moat assessment tables.

Revision ID: 054
Revises: 053
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- moat_assessments ---
    op.create_table(
        "moat_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("roic_above_wacc_years", sa.Integer()),
        sa.Column("roic_consistency_score", sa.Numeric(5, 2)),
        sa.Column("gross_margin_stability", sa.Numeric(5, 2)),
        sa.Column("gross_margin_10y_std", sa.Numeric(8, 4)),
        sa.Column("market_share_trend", sa.String(15)),
        sa.Column("market_share_5y_delta", sa.Numeric(8, 4)),
        sa.Column("customer_retention_proxy", sa.Numeric(5, 2)),
        sa.Column("moat_width", sa.String(6), nullable=False),
        sa.Column("moat_stability", sa.String(10)),
        sa.Column("moat_score", sa.Numeric(5, 2)),
        sa.Column("cost_advantage_score", sa.Numeric(5, 2)),
        sa.Column("network_effects_score", sa.Numeric(5, 2)),
        sa.Column("switching_costs_score", sa.Numeric(5, 2)),
        sa.Column("intangible_assets_score", sa.Numeric(5, 2)),
        sa.Column("efficient_scale_score", sa.Numeric(5, 2)),
        sa.Column("dominant_moat_source", sa.String(30)),
        sa.Column("moat_evidence", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "as_of_date", name="uq_ma_entity_date"),
    )
    op.create_index("idx_ma_entity", "moat_assessments", ["entity_id"])

    # --- moat_history ---
    op.create_table(
        "moat_history",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("moat_width", sa.String(6)),
        sa.Column("moat_score", sa.Numeric(5, 2)),
        sa.Column("roic", sa.Numeric(8, 4)),
        sa.Column("wacc", sa.Numeric(8, 4)),
        sa.Column("roic_wacc_spread", sa.Numeric(8, 4)),
        sa.Column("gross_margin", sa.Numeric(8, 4)),
        sa.Column("market_share_est", sa.Numeric(8, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "period_end_date", name="uq_mh_entity_period"),
    )
    op.create_index("idx_mh_entity", "moat_history", ["entity_id"])


def downgrade() -> None:
    op.drop_table("moat_history")
    op.drop_table("moat_assessments")
