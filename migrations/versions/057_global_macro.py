"""Pillar 3 Phase 3B Part 8: Central bank and global macro indicator tables.

Revision ID: 057
Revises: 056
"""

import sqlalchemy as sa
from alembic import op

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- central_bank_profiles ---
    op.create_table(
        "central_bank_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("bank_code", sa.String(10), nullable=False, unique=True),
        sa.Column("bank_name", sa.String(100)),
        sa.Column("country_code", sa.String(3)),
        sa.Column("current_rate", sa.Numeric(8, 4)),
        sa.Column("policy_stance", sa.String(10)),
        sa.Column("next_meeting_date", sa.Date()),
        sa.Column("forward_guidance_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- central_bank_decisions ---
    op.create_table(
        "central_bank_decisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("bank_code", sa.String(10), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("rate_before", sa.Numeric(8, 4)),
        sa.Column("rate_after", sa.Numeric(8, 4)),
        sa.Column("rate_change_bps", sa.Integer()),
        sa.Column("decision_type", sa.String(15)),
        sa.Column("was_surprise", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("vote_split", sa.String(50)),
        sa.Column("statement_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("bank_code", "decision_date", name="uq_cbd_bank_date"),
    )
    op.create_index("idx_cbd_bank", "central_bank_decisions", ["bank_code"])

    # --- global_macro_indicators ---
    op.create_table(
        "global_macro_indicators",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("indicator_type", sa.String(30)),
        sa.Column("period_label", sa.String(20)),
        sa.Column("value", sa.Numeric(15, 4)),
        sa.Column("prior_value", sa.Numeric(15, 4)),
        sa.Column("forecast_value", sa.Numeric(15, 4)),
        sa.Column("source", sa.String(30)),
        sa.Column("release_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_gmi_country", "global_macro_indicators", ["country_code"])


def downgrade() -> None:
    op.drop_table("global_macro_indicators")
    op.drop_table("central_bank_decisions")
    op.drop_table("central_bank_profiles")
