"""Financial Analysis Suite: congressional trades (STOCK Act).

Revision ID: 082
Revises: 081
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "082"
down_revision = "081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "congressional_trades",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("politician_name", sa.String(200), nullable=False),
        sa.Column("bioguide_id", sa.String(20)),
        sa.Column("chamber", sa.String(10)),
        sa.Column("party", sa.String(4)),
        sa.Column("state", sa.String(2)),
        sa.Column("ticker", sa.String(20)),
        sa.Column("security_id", sa.UUID(), sa.ForeignKey("securities.security_id")),
        sa.Column("asset_description", sa.String(400)),
        sa.Column("asset_type", sa.String(40)),
        sa.Column("transaction_type", sa.String(12), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("disclosure_date", sa.Date()),
        sa.Column("amount_range_low", sa.Numeric(18, 2)),
        sa.Column("amount_range_high", sa.Numeric(18, 2)),
        sa.Column("owner", sa.String(20)),
        sa.Column("disclosure_lag_days", sa.Integer()),
        sa.Column("is_late_disclosure", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("committees", JSONB()),
        sa.Column("source_url", sa.String(600)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_congress_trade_person_date", "congressional_trades", ["politician_name", "transaction_date"])
    op.create_index("idx_congress_trade_ticker_date", "congressional_trades", ["ticker", "transaction_date"])
    op.create_index("ix_congressional_trades_politician_name", "congressional_trades", ["politician_name"])
    op.create_index("ix_congressional_trades_bioguide_id", "congressional_trades", ["bioguide_id"])
    op.create_index("ix_congressional_trades_ticker", "congressional_trades", ["ticker"])
    op.create_index("ix_congressional_trades_transaction_date", "congressional_trades", ["transaction_date"])


def downgrade() -> None:
    op.drop_index("ix_congressional_trades_transaction_date", table_name="congressional_trades")
    op.drop_index("ix_congressional_trades_ticker", table_name="congressional_trades")
    op.drop_index("ix_congressional_trades_bioguide_id", table_name="congressional_trades")
    op.drop_index("ix_congressional_trades_politician_name", table_name="congressional_trades")
    op.drop_index("idx_congress_trade_ticker_date", table_name="congressional_trades")
    op.drop_index("idx_congress_trade_person_date", table_name="congressional_trades")
    op.drop_table("congressional_trades")
