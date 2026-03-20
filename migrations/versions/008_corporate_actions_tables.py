"""Create corporate actions tables (corporate_actions, dividend_actions, split_actions, ma_actions).

Revision ID: 008
Revises: 007
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- corporate_actions ---
    op.create_table(
        "corporate_actions",
        sa.Column("action_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("action_subtype", sa.String(50)),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("announcement_date", sa.Date()),
        sa.Column("ex_date", sa.Date()),
        sa.Column("record_date", sa.Date()),
        sa.Column("payment_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ca_action_type", "corporate_actions", ["action_type"])
    op.create_index("idx_ca_security_id", "corporate_actions", ["security_id"])
    op.create_index("idx_ca_entity_id", "corporate_actions", ["entity_id"])
    op.create_index("idx_ca_ex_date", "corporate_actions", ["ex_date"])
    op.create_index("idx_ca_status", "corporate_actions", ["status"])
    op.create_index("idx_ca_security_date", "corporate_actions", ["security_id", "ex_date"])
    op.create_index("idx_ca_type_status", "corporate_actions", ["action_type", "status"])

    # --- dividend_actions ---
    op.create_table(
        "dividend_actions",
        sa.Column("action_id", UUID(as_uuid=True), sa.ForeignKey("corporate_actions.action_id"), primary_key=True),
        sa.Column("dividend_type", sa.String(30), nullable=False),
        sa.Column("frequency", sa.String(20)),
        sa.Column("gross_amount", sa.Numeric(10, 6)),
        sa.Column("currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("tax_rate", sa.Numeric(5, 4)),
        sa.Column("qualified", sa.Boolean()),
        sa.Column("stock_dividend_ratio", sa.Numeric(10, 6)),
    )

    # --- split_actions ---
    op.create_table(
        "split_actions",
        sa.Column("action_id", UUID(as_uuid=True), sa.ForeignKey("corporate_actions.action_id"), primary_key=True),
        sa.Column("split_ratio_from", sa.Integer(), nullable=False),
        sa.Column("split_ratio_to", sa.Integer(), nullable=False),
        sa.Column("split_factor", sa.Numeric(10, 6)),
        sa.Column("adjustment_factor", sa.Numeric(18, 10)),
    )

    # --- ma_actions ---
    op.create_table(
        "ma_actions",
        sa.Column("action_id", UUID(as_uuid=True), sa.ForeignKey("corporate_actions.action_id"), primary_key=True),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("acquirer_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("target_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("deal_value", sa.Numeric(20, 2)),
        sa.Column("deal_currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("price_per_share", sa.Numeric(18, 6)),
        sa.Column("cash_component", sa.Numeric(18, 6)),
        sa.Column("stock_component", sa.Numeric(18, 6)),
        sa.Column("consideration_type", sa.String(20)),
        sa.Column("premium_1day", sa.Numeric(8, 4)),
        sa.Column("premium_30day", sa.Numeric(8, 4)),
        sa.Column("conditions", JSONB),
        sa.Column("termination_fee", sa.Numeric(20, 2)),
    )


def downgrade() -> None:
    op.drop_table("ma_actions")
    op.drop_table("split_actions")
    op.drop_table("dividend_actions")
    op.drop_table("corporate_actions")
