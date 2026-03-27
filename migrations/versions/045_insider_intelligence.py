"""Pillar 3 Phase 1: Insider transactions and aggregate signals.

Revision ID: 045
Revises: 044
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- insider_transactions_p3 ---
    op.create_table(
        "insider_transactions_p3",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("reporting_person", sa.String(200), nullable=False),
        sa.Column("reporting_person_cik", sa.String(10)),
        sa.Column("relationship", sa.String(30), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("transaction_code", sa.String(2)),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("shares", sa.Numeric(15, 2)),
        sa.Column("price_per_share", sa.Numeric(12, 4)),
        sa.Column("total_value", sa.Numeric(18, 2)),
        sa.Column("shares_owned_after", sa.Numeric(15, 2)),
        sa.Column("is_open_market", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_10b5_1", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_direct_ownership", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("filing_date", sa.Date()),
        sa.Column("filing_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_insider_tx_entity_date",
        "insider_transactions_p3",
        ["entity_id", "transaction_date"],
    )
    op.create_index(
        "idx_insider_tx_person_date",
        "insider_transactions_p3",
        ["reporting_person_cik", "transaction_date"],
    )

    # --- insider_signals ---
    op.create_table(
        "insider_signals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column("signal_strength", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("net_shares_30d", sa.Numeric(15, 2)),
        sa.Column("net_value_30d", sa.Numeric(18, 2)),
        sa.Column("net_shares_90d", sa.Numeric(15, 2)),
        sa.Column("net_value_90d", sa.Numeric(18, 2)),
        sa.Column("net_shares_365d", sa.Numeric(15, 2)),
        sa.Column("net_value_365d", sa.Numeric(18, 2)),
        sa.Column("open_market_buy_count_90d", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("insider_count_buying_30d", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("insider_count_selling_30d", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ownership_pct_change", sa.Numeric(8, 4)),
        sa.Column("detail", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_insider_signal",
        "insider_signals",
        ["entity_id", "signal_date", "signal_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("insider_signals")
    op.drop_table("insider_transactions_p3")
