"""Pillar 3 Phase 3C Part 14: FI intelligence tables.

Revision ID: 060
Revises: 059
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- fi_market_briefings ---
    op.create_table(
        "fi_market_briefings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("briefing_type", sa.String(20)),
        sa.Column("ig_oas_bps", sa.Numeric(8, 2)),
        sa.Column("hy_oas_bps", sa.Numeric(8, 2)),
        sa.Column("ig_oas_1w_change", sa.Numeric(8, 2)),
        sa.Column("hy_oas_1w_change", sa.Numeric(8, 2)),
        sa.Column("credit_regime", sa.String(15)),
        sa.Column("spread_2s10s_bps", sa.Numeric(8, 2)),
        sa.Column("spread_3m10y_bps", sa.Numeric(8, 2)),
        sa.Column("curve_shape", sa.String(15)),
        sa.Column("fallen_angels_this_period", JSONB),
        sa.Column("rising_stars_this_period", JSONB),
        sa.Column("narrative", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- new_issuance_events ---
    op.create_table(
        "new_issuance_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("coupon_rate", sa.Numeric(8, 4)),
        sa.Column("maturity_date", sa.Date()),
        sa.Column("size_mm", sa.Numeric(15, 2)),
        sa.Column("spread_at_issue_bps", sa.Numeric(8, 2)),
        sa.Column("initial_talk_bps", sa.Numeric(8, 2)),
        sa.Column("rating", sa.String(10)),
        sa.Column("use_of_proceeds", sa.String(30)),
        sa.Column("oversubscribed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_nie_entity", "new_issuance_events", ["entity_id"])

    # --- cross_asset_signals ---
    op.create_table(
        "cross_asset_signals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("signal_type", sa.String(30)),
        sa.Column("equity_return_pct", sa.Numeric(8, 4)),
        sa.Column("spread_change_bps", sa.Numeric(8, 2)),
        sa.Column("severity", sa.String(10)),
        sa.Column("narrative", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_cas_entity", "cross_asset_signals", ["entity_id"])


def downgrade() -> None:
    op.drop_table("cross_asset_signals")
    op.drop_table("new_issuance_events")
    op.drop_table("fi_market_briefings")
