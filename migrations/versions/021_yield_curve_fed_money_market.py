"""Yield curve, Fed meetings, and money market rates.

Revision ID: 021
Revises: 020
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # yield_curve_snapshots
    op.create_table(
        "yield_curve_snapshots",
        sa.Column("curve_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("curve_date", sa.Date(), nullable=False),
        sa.Column("curve_type", sa.String(25), nullable=False),
        sa.Column("rate_1m", sa.Numeric(8, 4)),
        sa.Column("rate_3m", sa.Numeric(8, 4)),
        sa.Column("rate_6m", sa.Numeric(8, 4)),
        sa.Column("rate_1y", sa.Numeric(8, 4)),
        sa.Column("rate_2y", sa.Numeric(8, 4)),
        sa.Column("rate_3y", sa.Numeric(8, 4)),
        sa.Column("rate_5y", sa.Numeric(8, 4)),
        sa.Column("rate_7y", sa.Numeric(8, 4)),
        sa.Column("rate_10y", sa.Numeric(8, 4)),
        sa.Column("rate_20y", sa.Numeric(8, 4)),
        sa.Column("rate_30y", sa.Numeric(8, 4)),
        sa.Column("spread_2s10s", sa.Numeric(8, 4)),
        sa.Column("spread_3m10y", sa.Numeric(8, 4)),
        sa.Column("curve_slope", sa.Numeric(8, 4)),
        sa.Column("is_inverted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_yc_date_type", "yield_curve_snapshots", ["curve_date", "curve_type"], unique=True)

    # zero_coupon_curves
    op.create_table(
        "zero_coupon_curves",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("curve_date", sa.Date(), nullable=False),
        sa.Column("tenor_years", sa.Numeric(6, 2), nullable=False),
        sa.Column("zero_rate", sa.Numeric(8, 6)),
        sa.Column("discount_factor", sa.Numeric(12, 8)),
        sa.Column("forward_rate", sa.Numeric(8, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_zc_date_tenor", "zero_coupon_curves", ["curve_date", "tenor_years"], unique=True)

    # fed_meetings
    op.create_table(
        "fed_meetings",
        sa.Column("meeting_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("meeting_date", sa.Date(), nullable=False, unique=True),
        sa.Column("meeting_type", sa.String(15)),
        sa.Column("rate_decision", sa.String(10)),
        sa.Column("fed_funds_lower", sa.Numeric(6, 4)),
        sa.Column("fed_funds_upper", sa.Numeric(6, 4)),
        sa.Column("change_bps", sa.Integer()),
        sa.Column("statement_text", sa.Text()),
        sa.Column("statement_url", sa.String(500)),
        sa.Column("minutes_url", sa.String(500)),
        sa.Column("minutes_release_date", sa.Date()),
        sa.Column("total_assets", sa.Numeric(20, 2)),
        sa.Column("treasury_holdings", sa.Numeric(20, 2)),
        sa.Column("mbs_holdings", sa.Numeric(20, 2)),
        sa.Column("dot_plot_data", JSONB()),
        sa.Column("policy_id", UUID(as_uuid=True), sa.ForeignKey("central_bank_policies.policy_id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # money_market_rates
    op.create_table(
        "money_market_rates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate_type", sa.String(30), nullable=False),
        sa.Column("rate_value", sa.Numeric(8, 6)),
        sa.Column("source", sa.String(20), server_default="FRED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mmr_date_type", "money_market_rates", ["rate_date", "rate_type"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_mmr_date_type", table_name="money_market_rates")
    op.drop_table("money_market_rates")
    op.drop_table("fed_meetings")
    op.drop_index("idx_zc_date_tenor", table_name="zero_coupon_curves")
    op.drop_table("zero_coupon_curves")
    op.drop_index("idx_yc_date_type", table_name="yield_curve_snapshots")
    op.drop_table("yield_curve_snapshots")
