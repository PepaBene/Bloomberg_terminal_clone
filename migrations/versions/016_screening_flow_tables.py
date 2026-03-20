"""Create screening and institutional flow tables.

Revision ID: 016
Revises: 015
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Saved Screens ────────────────────────────────────────────────
    op.create_table(
        "saved_screens",
        sa.Column("screen_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("screen_type", sa.String(20), nullable=False, server_default="CUSTOM"),
        sa.Column("is_prebuilt", sa.Boolean, server_default="false"),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("universe", sa.String(30), server_default="ALL"),
        sa.Column("created_by", sa.String(100)),
        sa.Column("tags", JSONB),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_saved_screens_type", "saved_screens", ["screen_type"])
    op.create_index("idx_saved_screens_prebuilt", "saved_screens", ["is_prebuilt"])

    # ── Institutional Flow Signals ───────────────────────────────────
    op.create_table(
        "institutional_flow_signals",
        sa.Column("signal_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("new_positions_count", sa.Integer),
        sa.Column("closed_positions_count", sa.Integer),
        sa.Column("increased_positions_count", sa.Integer),
        sa.Column("decreased_positions_count", sa.Integer),
        sa.Column("unchanged_positions_count", sa.Integer),
        sa.Column("net_shares_change", sa.Numeric(20, 2)),
        sa.Column("net_value_change", sa.Numeric(20, 2)),
        sa.Column("buy_sell_ratio", sa.Numeric(8, 4)),
        sa.Column("breadth_score", sa.Numeric(8, 4)),
        sa.Column("conviction_score", sa.Numeric(8, 4)),
        sa.Column("whale_net_shares", sa.Numeric(20, 2)),
        sa.Column("whale_net_value", sa.Numeric(20, 2)),
        sa.Column("smart_money_flow", sa.Numeric(8, 4)),
        sa.Column("flow_trend_3q", sa.String(20)),
        sa.Column("flow_trend_4q", sa.String(20)),
        sa.Column("short_interest_ratio", sa.Numeric(8, 4)),
        sa.Column("days_to_cover", sa.Numeric(8, 2)),
        sa.Column("squeeze_potential", sa.String(20)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("inputs", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_flow_signals_security_date", "institutional_flow_signals", ["security_id", "report_date"])
    op.create_index("idx_flow_signals_date", "institutional_flow_signals", ["report_date"])

    # ── Institution Analytics ────────────────────────────────────────
    op.create_table(
        "institution_analytics",
        sa.Column("analytics_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institution_profiles.institution_id"), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("investment_style", sa.String(30)),
        sa.Column("concentration_score", sa.Numeric(8, 4)),
        sa.Column("turnover_rate", sa.Numeric(8, 4)),
        sa.Column("total_positions", sa.Integer),
        sa.Column("new_positions", sa.Integer),
        sa.Column("closed_positions", sa.Integer),
        sa.Column("total_value", sa.Numeric(20, 2)),
        sa.Column("top_holdings", JSONB),
        sa.Column("sector_allocation", JSONB),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_inst_analytics_institution_date", "institution_analytics", ["institution_id", "report_date"])

    # ── Flow Alerts ──────────────────────────────────────────────────
    op.create_table(
        "flow_alerts",
        sa.Column("alert_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institution_profiles.institution_id")),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("shares_involved", sa.Numeric(20, 2)),
        sa.Column("value_involved", sa.Numeric(20, 2)),
        sa.Column("percent_of_outstanding", sa.Numeric(8, 4)),
        sa.Column("details", JSONB),
        sa.Column("severity", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_flow_alerts_type_date", "flow_alerts", ["alert_type", "report_date"])
    op.create_index("idx_flow_alerts_security", "flow_alerts", ["security_id"])


def downgrade() -> None:
    op.drop_table("flow_alerts")
    op.drop_table("institution_analytics")
    op.drop_table("institutional_flow_signals")
    op.drop_table("saved_screens")
