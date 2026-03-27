"""Pillar 4 Phase 1: Portfolio management core table.

Revision ID: 071
Revises: 070
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("portfolio_name", sa.String(200), nullable=False),
        sa.Column("portfolio_type", sa.String(10), nullable=False, server_default="REAL"),
        sa.Column("benchmark_id", sa.String(20)),
        sa.Column("inception_date", sa.Date, nullable=False),
        sa.Column("base_currency", sa.String(3), server_default="USD"),
        sa.Column("initial_cash", sa.Numeric(20, 2), nullable=False),
        sa.Column("current_cash", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(10), server_default="ACTIVE"),
        sa.Column("tags", JSONB),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "portfolio_name", name="uq_portfolio_user_name"),
    )


def downgrade() -> None:
    op.drop_table("portfolios")
