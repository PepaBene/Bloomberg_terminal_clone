"""Corporate bonds and TRACE pricing tables.

Revision ID: 037
Revises: 036
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. corporate_bonds
    op.create_table(
        "corporate_bonds",
        sa.Column("bond_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("cusip", sa.String(9), nullable=False, unique=True),
        sa.Column("isin", sa.String(12)),
        sa.Column("figi", sa.String(12)),
        sa.Column("issuer_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("issuer_name", sa.String(500)),
        sa.Column("issuer_cik", sa.String(10)),
        sa.Column("security_id", UUID(as_uuid=True)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("coupon_rate", sa.Numeric(8, 6)),
        sa.Column("coupon_type", sa.String(20)),
        sa.Column("coupon_frequency", sa.Integer),
        sa.Column("day_count_convention", sa.String(20)),
        sa.Column("floating_reference_rate", sa.String(20)),
        sa.Column("floating_spread_bps", sa.Integer),
        sa.Column("issue_date", sa.Date),
        sa.Column("maturity_date", sa.Date, nullable=False),
        sa.Column("first_coupon_date", sa.Date),
        sa.Column("original_issue_amount", sa.Numeric(20, 2)),
        sa.Column("outstanding_amount", sa.Numeric(20, 2)),
        sa.Column("minimum_denomination", sa.Numeric(20, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("seniority", sa.String(30)),
        sa.Column("collateral_type", sa.String(200)),
        sa.Column("is_guaranteed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("guarantor_entity_id", UUID(as_uuid=True)),
        sa.Column("is_callable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("callable_from_date", sa.Date),
        sa.Column("call_type", sa.String(20)),
        sa.Column("is_puttable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_convertible", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("conversion_price", sa.Numeric(10, 4)),
        sa.Column("initial_rating_sp", sa.String(10)),
        sa.Column("initial_rating_moodys", sa.String(10)),
        sa.Column("initial_rating_fitch", sa.String(10)),
        sa.Column("is_investment_grade", sa.Boolean),
        sa.Column("use_of_proceeds", sa.String(30)),
        sa.Column("use_of_proceeds_text", sa.String(200)),
        sa.Column("has_change_of_control_put", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("has_negative_pledge", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("has_leverage_covenant", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("has_interest_coverage_covenant", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source_filing_accession", sa.String(25)),
        sa.Column("source_filing_type", sa.String(10)),
        sa.Column("source_filing_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False, server_default="OUTSTANDING"),
        sa.Column("status_date", sa.Date),
        sa.Column("status_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_corp_bond_cusip", "corporate_bonds", ["cusip"])
    op.create_index("idx_corp_bond_issuer", "corporate_bonds", ["issuer_entity_id"])
    op.create_index("idx_corp_bond_maturity", "corporate_bonds", ["maturity_date"])
    op.create_index("idx_corp_bond_status", "corporate_bonds", ["status"])

    # 2. bond_call_schedules
    op.create_table(
        "bond_call_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bond_id", UUID(as_uuid=True), sa.ForeignKey("corporate_bonds.bond_id"), nullable=False),
        sa.Column("call_date", sa.Date, nullable=False),
        sa.Column("call_price", sa.Numeric(10, 4)),
        sa.Column("call_type", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_call_schedule_bond", "bond_call_schedules", ["bond_id"])

    # 3. bond_trades
    op.create_table(
        "bond_trades",
        sa.Column("trade_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bond_id", UUID(as_uuid=True), sa.ForeignKey("corporate_bonds.bond_id"), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("trade_time", sa.Time),
        sa.Column("settlement_date", sa.Date),
        sa.Column("price", sa.Numeric(10, 6)),
        sa.Column("yield_value", sa.Numeric(8, 6)),
        sa.Column("quantity", sa.Numeric(20, 2)),
        sa.Column("quantity_reported", sa.String(10)),
        sa.Column("trade_type", sa.String(20)),
        sa.Column("is_when_issued", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_bond_trade_bond_date", "bond_trades", ["bond_id", "trade_date"])

    # 4. bond_eod_prices
    op.create_table(
        "bond_eod_prices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bond_id", UUID(as_uuid=True), sa.ForeignKey("corporate_bonds.bond_id"), nullable=False),
        sa.Column("price_date", sa.Date, nullable=False),
        sa.Column("last_trade_price", sa.Numeric(10, 6)),
        sa.Column("vwap", sa.Numeric(10, 6)),
        sa.Column("high_price", sa.Numeric(10, 6)),
        sa.Column("low_price", sa.Numeric(10, 6)),
        sa.Column("trade_count", sa.Integer),
        sa.Column("total_volume", sa.Numeric(20, 2)),
        sa.Column("yield_to_maturity", sa.Numeric(8, 6)),
        sa.Column("yield_to_worst", sa.Numeric(8, 6)),
        sa.Column("g_spread_bps", sa.Integer),
        sa.Column("treasury_benchmark_cusip", sa.String(9)),
        sa.Column("liquidity_score", sa.Integer),
        sa.Column("has_sufficient_trades", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("price_source", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_bond_eod_bond_date", "bond_eod_prices", ["bond_id", "price_date"], unique=True)


def downgrade() -> None:
    op.drop_table("bond_eod_prices")
    op.drop_table("bond_trades")
    op.drop_table("bond_call_schedules")
    op.drop_table("corporate_bonds")
