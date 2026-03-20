"""Create ownership tables (institutions, holdings, insiders, summaries, short interest).

Revision ID: 009
Revises: 008
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- institution_profiles ---
    op.create_table(
        "institution_profiles",
        sa.Column("institution_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), unique=True, nullable=True),
        sa.Column("cik", sa.String(10)),
        sa.Column("institution_name", sa.String(300), nullable=False, index=True),
        sa.Column("institution_type", sa.String(30), index=True),
        sa.Column("tier", sa.String(10)),
        sa.Column("aum", sa.Numeric(20, 2)),
        sa.Column("number_of_holdings", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- institutional_holdings ---
    op.create_table(
        "institutional_holdings",
        sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institution_profiles.institution_id"), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), primary_key=True),
        sa.Column("report_date", sa.Date(), primary_key=True),
        sa.Column("filing_date", sa.Date()),
        sa.Column("shares_held", sa.Numeric(20, 2)),
        sa.Column("market_value", sa.Numeric(20, 2)),
        sa.Column("percent_of_portfolio", sa.Numeric(8, 4)),
        sa.Column("percent_of_outstanding", sa.Numeric(8, 4)),
        sa.Column("shares_change", sa.Numeric(20, 2)),
        sa.Column("is_new_position", sa.Boolean()),
        sa.Column("is_sold_out", sa.Boolean()),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_institutional_holdings_security", "institutional_holdings", ["security_id"])
    op.create_index("idx_institutional_holdings_report_date", "institutional_holdings", ["report_date"])

    # --- insider_holdings ---
    op.create_table(
        "insider_holdings",
        sa.Column("transaction_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), index=True),
        sa.Column("insider_name", sa.String(200)),
        sa.Column("insider_title", sa.String(100)),
        sa.Column("insider_relationship", sa.String(30)),
        sa.Column("transaction_type", sa.String(20)),
        sa.Column("transaction_date", sa.Date(), index=True),
        sa.Column("shares_transacted", sa.Numeric(20, 2)),
        sa.Column("price_per_share", sa.Numeric(18, 6)),
        sa.Column("total_value", sa.Numeric(20, 2)),
        sa.Column("shares_owned_after", sa.Numeric(20, 2)),
        sa.Column("ownership_nature", sa.String(10)),
    )
    op.create_index("idx_insider_holdings_security_date", "insider_holdings", ["security_id", "transaction_date"])

    # --- ownership_summaries ---
    op.create_table(
        "ownership_summaries",
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), primary_key=True),
        sa.Column("report_date", sa.Date(), primary_key=True),
        sa.Column("institutional_holders_count", sa.Integer()),
        sa.Column("institutional_shares", sa.Numeric(20, 2)),
        sa.Column("insider_shares", sa.Numeric(20, 2)),
        sa.Column("institutional_percent", sa.Numeric(8, 4)),
        sa.Column("insider_percent", sa.Numeric(8, 4)),
        sa.Column("top_10_concentration", sa.Numeric(8, 4)),
    )
    op.create_index("idx_ownership_summaries_security", "ownership_summaries", ["security_id"])

    # --- short_interest ---
    op.create_table(
        "short_interest",
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), primary_key=True),
        sa.Column("settlement_date", sa.Date(), primary_key=True),
        sa.Column("shares_short", sa.Numeric(20, 2)),
        sa.Column("short_percent_float", sa.Numeric(8, 4)),
        sa.Column("short_percent_outstanding", sa.Numeric(8, 4)),
        sa.Column("days_to_cover", sa.Numeric(8, 2)),
        sa.Column("source", sa.String(30)),
    )
    op.create_index("idx_short_interest_security", "short_interest", ["security_id"])


def downgrade() -> None:
    op.drop_table("short_interest")
    op.drop_table("ownership_summaries")
    op.drop_index("idx_insider_holdings_security_date", table_name="insider_holdings")
    op.drop_table("insider_holdings")
    op.drop_table("institutional_holdings")
    op.drop_table("institution_profiles")
