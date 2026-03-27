"""Pillar 4 Phase 1: Transaction log and audit trail.

Revision ID: 073
Revises: 072
"""

import sqlalchemy as sa
from alembic import op

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("security_id", sa.UUID()),
        sa.Column("ticker", sa.String(20)),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("settlement_date", sa.Date),
        sa.Column("shares", sa.Numeric(20, 6)),
        sa.Column("price_per_share", sa.Numeric(15, 6)),
        sa.Column("gross_amount", sa.Numeric(20, 2)),
        sa.Column("commission", sa.Numeric(12, 2), server_default=sa.text("0")),
        sa.Column("net_amount", sa.Numeric(20, 2)),
        sa.Column("cash_impact", sa.Numeric(20, 2)),
        sa.Column("source", sa.String(20), server_default="MANUAL"),
        sa.Column("source_reference", sa.String(200)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_txn_portfolio_date", "transactions", ["portfolio_id", "transaction_date"])


def downgrade() -> None:
    op.drop_index("idx_txn_portfolio_date", table_name="transactions")
    op.drop_table("transactions")
