"""Pillar 4 Phase 1: NAV snapshots and corporate action queue.

Revision ID: 074
Revises: 073
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nav_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("nav", sa.Numeric(20, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 2)),
        sa.Column("cash_balance", sa.Numeric(20, 2)),
        sa.Column("unrealized_pnl", sa.Numeric(20, 2)),
        sa.Column("daily_return", sa.Numeric(12, 8)),
        sa.Column("cumulative_return", sa.Numeric(12, 8)),
        sa.Column("benchmark_daily_return", sa.Numeric(12, 8)),
        sa.Column("benchmark_cumulative_return", sa.Numeric(12, 8)),
        sa.Column("positions_snapshot", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_nav_portfolio_date"),
    )

    op.create_table(
        "corporate_action_queue",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("position_id", sa.UUID()),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("security_id", sa.UUID()),
        sa.Column("ticker", sa.String(20)),
        sa.Column("ex_date", sa.Date),
        sa.Column("payment_date", sa.Date),
        sa.Column("details", JSONB),
        sa.Column("status", sa.String(15), server_default="PENDING"),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("corporate_action_queue")
    op.drop_table("nav_snapshots")
