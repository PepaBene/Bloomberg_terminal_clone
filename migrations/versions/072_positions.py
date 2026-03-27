"""Pillar 4 Phase 1: Position tracking for portfolios.

Revision ID: 072
Revises: 071
"""

import sqlalchemy as sa
from alembic import op

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), nullable=False, index=True),
        sa.Column("security_id", sa.UUID()),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), server_default="OPEN"),
        sa.Column("shares", sa.Numeric(20, 6)),
        sa.Column("cost_basis_total", sa.Numeric(20, 2)),
        sa.Column("cost_basis_per_share", sa.Numeric(15, 6)),
        sa.Column("first_acquisition_date", sa.Date),
        sa.Column("market_value", sa.Numeric(20, 2)),
        sa.Column("unrealized_pnl", sa.Numeric(20, 2)),
        sa.Column("unrealized_pnl_pct", sa.Numeric(10, 4)),
        sa.Column("weight", sa.Numeric(8, 4)),
        sa.Column("closing_price", sa.Numeric(15, 4)),
        sa.Column("day_change_pct", sa.Numeric(10, 4)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "ticker", "status", name="uq_position_portfolio_ticker_status"),
    )


def downgrade() -> None:
    op.drop_table("positions")
