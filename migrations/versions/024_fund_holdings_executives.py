"""Fund holdings and executives.

Revision ID: 024
Revises: 023
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # funds
    op.create_table(
        "funds",
        sa.Column("fund_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("fund_name", sa.String(300), nullable=False),
        sa.Column("fund_ticker", sa.String(20)),
        sa.Column("series_id", sa.String(30)),
        sa.Column("class_id", sa.String(30)),
        sa.Column("cik", sa.String(10)),
        sa.Column("fund_type", sa.String(20)),
        sa.Column("strategy", sa.String(100)),
        sa.Column("category", sa.String(100)),
        sa.Column("total_net_assets", sa.Numeric(20, 2)),
        sa.Column("number_of_holdings", sa.Integer()),
        sa.Column("top_10_concentration", sa.Numeric(8, 4)),
        sa.Column("expense_ratio", sa.Numeric(8, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_fund_ticker", "funds", ["fund_ticker"])
    op.create_index("idx_fund_cik", "funds", ["cik"])
    op.create_index("idx_fund_type", "funds", ["fund_type"])

    # fund_holdings
    op.create_table(
        "fund_holdings",
        sa.Column("holding_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.fund_id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("security_name", sa.String(300)),
        sa.Column("cusip", sa.String(9)),
        sa.Column("isin", sa.String(12)),
        sa.Column("quantity", sa.Numeric(20, 4)),
        sa.Column("market_value", sa.Numeric(20, 2)),
        sa.Column("pct_of_nav", sa.Numeric(8, 4)),
        sa.Column("asset_type", sa.String(20)),
        sa.Column("issuer_category", sa.String(20)),
        sa.Column("nport_accession", sa.String(25)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_holding_fund", "fund_holdings", ["fund_id"])
    op.create_index("idx_holding_fund_date", "fund_holdings", ["fund_id", "report_date"])
    op.create_index("idx_holding_security_date", "fund_holdings", ["security_id", "report_date"])

    # executives
    op.create_table(
        "executives",
        sa.Column("executive_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("person_name", sa.String(200), nullable=False),
        sa.Column("bio_text", sa.Text()),
        sa.Column("education", JSONB()),
        sa.Column("age", sa.Integer()),
        sa.Column("total_compensation", sa.Numeric(20, 2)),
        sa.Column("base_salary", sa.Numeric(20, 2)),
        sa.Column("bonus", sa.Numeric(20, 2)),
        sa.Column("stock_awards", sa.Numeric(20, 2)),
        sa.Column("option_awards", sa.Numeric(20, 2)),
        sa.Column("other_compensation", sa.Numeric(20, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_exec_name", "executives", ["person_name"])

    # executive_roles
    op.create_table(
        "executive_roles",
        sa.Column("role_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("executive_id", UUID(as_uuid=True), sa.ForeignKey("executives.executive_id"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("role_type", sa.String(10)),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("is_independent", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_role_executive", "executive_roles", ["executive_id"])
    op.create_index("idx_role_entity", "executive_roles", ["entity_id"])
    op.create_index("idx_role_entity_type", "executive_roles", ["entity_id", "role_type"])


def downgrade() -> None:
    op.drop_index("idx_role_entity_type", table_name="executive_roles")
    op.drop_index("idx_role_entity", table_name="executive_roles")
    op.drop_index("idx_role_executive", table_name="executive_roles")
    op.drop_table("executive_roles")
    op.drop_index("idx_exec_name", table_name="executives")
    op.drop_table("executives")
    op.drop_index("idx_holding_security_date", table_name="fund_holdings")
    op.drop_index("idx_holding_fund_date", table_name="fund_holdings")
    op.drop_index("idx_holding_fund", table_name="fund_holdings")
    op.drop_table("fund_holdings")
    op.drop_index("idx_fund_type", table_name="funds")
    op.drop_index("idx_fund_cik", table_name="funds")
    op.drop_index("idx_fund_ticker", table_name="funds")
    op.drop_table("funds")
