"""M&A deals and IPO events.

Revision ID: 022
Revises: 021
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ma_deals
    op.create_table(
        "ma_deals",
        sa.Column("deal_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("acquirer_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("target_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("acquirer_name", sa.String(200)),
        sa.Column("target_name", sa.String(200)),
        sa.Column("deal_type", sa.String(25)),
        sa.Column("deal_status", sa.String(15)),
        sa.Column("is_hostile", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_value", sa.Numeric(20, 2)),
        sa.Column("equity_value", sa.Numeric(20, 2)),
        sa.Column("price_per_share", sa.Numeric(12, 4)),
        sa.Column("premium_to_undisturbed", sa.Numeric(8, 4)),
        sa.Column("payment_type", sa.String(10)),
        sa.Column("cash_component", sa.Numeric(20, 2)),
        sa.Column("stock_exchange_ratio", sa.Numeric(10, 6)),
        sa.Column("ev_to_revenue", sa.Numeric(10, 4)),
        sa.Column("ev_to_ebitda", sa.Numeric(10, 4)),
        sa.Column("pe_ratio", sa.Numeric(10, 4)),
        sa.Column("target_revenue_ltm", sa.Numeric(20, 2)),
        sa.Column("target_ebitda_ltm", sa.Numeric(20, 2)),
        sa.Column("target_net_income_ltm", sa.Numeric(20, 2)),
        sa.Column("announcement_date", sa.Date()),
        sa.Column("completion_date", sa.Date()),
        sa.Column("termination_date", sa.Date()),
        sa.Column("expected_completion", sa.Date()),
        sa.Column("acquirer_financial_advisors", JSONB()),
        sa.Column("target_financial_advisors", JSONB()),
        sa.Column("acquirer_legal_counsel", JSONB()),
        sa.Column("target_legal_counsel", JSONB()),
        sa.Column("regulatory_approvals_required", JSONB()),
        sa.Column("regulatory_status", sa.String(30)),
        sa.Column("target_gics_sector", sa.String(100)),
        sa.Column("target_gics_industry", sa.String(100)),
        sa.Column("source_filings", JSONB()),
        sa.Column("primary_source", sa.String(20)),
        sa.Column("corporate_action_id", UUID(as_uuid=True), sa.ForeignKey("corporate_actions.action_id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_deal_acquirer", "ma_deals", ["acquirer_entity_id"])
    op.create_index("idx_deal_target", "ma_deals", ["target_entity_id"])
    op.create_index("idx_deal_status", "ma_deals", ["deal_status"])
    op.create_index("idx_deal_announcement", "ma_deals", ["announcement_date"])
    op.create_index("idx_deal_sector", "ma_deals", ["target_gics_sector"])

    # ipo_events
    op.create_table(
        "ipo_events",
        sa.Column("ipo_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("s1_filing_date", sa.Date()),
        sa.Column("s1_accession_number", sa.String(25)),
        sa.Column("pricing_date", sa.Date()),
        sa.Column("trading_start_date", sa.Date()),
        sa.Column("initial_range_low", sa.Numeric(12, 4)),
        sa.Column("initial_range_high", sa.Numeric(12, 4)),
        sa.Column("offer_price", sa.Numeric(12, 4)),
        sa.Column("shares_offered", sa.Numeric(20, 0)),
        sa.Column("total_proceeds", sa.Numeric(20, 2)),
        sa.Column("overallotment_shares", sa.Numeric(20, 0)),
        sa.Column("first_day_close", sa.Numeric(12, 4)),
        sa.Column("first_day_return_pct", sa.Numeric(8, 4)),
        sa.Column("current_price", sa.Numeric(12, 4)),
        sa.Column("return_vs_offer_pct", sa.Numeric(8, 4)),
        sa.Column("lead_underwriters", JSONB()),
        sa.Column("co_managers", JSONB()),
        sa.Column("company_description", sa.Text()),
        sa.Column("gics_sector", sa.String(100)),
        sa.Column("gics_industry", sa.String(100)),
        sa.Column("revenue_ltm", sa.Numeric(20, 2)),
        sa.Column("net_income_ltm", sa.Numeric(20, 2)),
        sa.Column("status", sa.String(15)),
        sa.Column("withdrawal_date", sa.Date()),
        sa.Column("withdrawal_reason", sa.Text()),
        sa.Column("source_filings", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_ipo_entity", "ipo_events", ["entity_id"])
    op.create_index("idx_ipo_status", "ipo_events", ["status"])
    op.create_index("idx_ipo_pricing_date", "ipo_events", ["pricing_date"])


def downgrade() -> None:
    op.drop_index("idx_ipo_pricing_date", table_name="ipo_events")
    op.drop_index("idx_ipo_status", table_name="ipo_events")
    op.drop_index("idx_ipo_entity", table_name="ipo_events")
    op.drop_table("ipo_events")
    op.drop_index("idx_deal_sector", table_name="ma_deals")
    op.drop_index("idx_deal_announcement", table_name="ma_deals")
    op.drop_index("idx_deal_status", table_name="ma_deals")
    op.drop_index("idx_deal_target", table_name="ma_deals")
    op.drop_index("idx_deal_acquirer", table_name="ma_deals")
    op.drop_table("ma_deals")
