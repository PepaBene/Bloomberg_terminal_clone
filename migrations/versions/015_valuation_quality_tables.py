"""Create Pillar 2 valuation and quality scoring tables.

Revision ID: 015
Revises: 014
Create Date: 2026-03-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── DCF Results ───────────────────────────────────────────────────
    op.create_table(
        "dcf_results",
        sa.Column("dcf_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("assumptions", JSONB),
        sa.Column("wacc_used", sa.Numeric(8, 4)),
        sa.Column("cost_of_equity", sa.Numeric(8, 4)),
        sa.Column("projected_cashflows", JSONB),
        sa.Column("terminal_value", sa.Numeric(20, 2)),
        sa.Column("terminal_method", sa.String(20)),
        sa.Column("terminal_growth_rate", sa.Numeric(6, 4)),
        sa.Column("terminal_exit_multiple", sa.Numeric(8, 2)),
        sa.Column("pv_terminal", sa.Numeric(20, 2)),
        sa.Column("terminal_pct_of_ev", sa.Numeric(6, 4)),
        sa.Column("pv_of_fcf", sa.Numeric(20, 2)),
        sa.Column("enterprise_value", sa.Numeric(20, 2)),
        sa.Column("net_debt", sa.Numeric(20, 2)),
        sa.Column("equity_value", sa.Numeric(20, 2)),
        sa.Column("shares_outstanding", sa.Numeric(20, 2)),
        sa.Column("implied_price", sa.Numeric(18, 6)),
        sa.Column("current_price", sa.Numeric(18, 6)),
        sa.Column("upside_downside_pct", sa.Numeric(8, 4)),
        sa.Column("sensitivity_grid", JSONB),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("currency", sa.String(3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_dcf_entity_date", "dcf_results", ["entity_id", "calculation_date"])
    op.create_index("idx_dcf_security_date", "dcf_results", ["security_id", "calculation_date"])

    # ── Comps Results ─────────────────────────────────────────────────
    op.create_table(
        "comps_results",
        sa.Column("comps_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("peer_security_ids", JSONB),
        sa.Column("peer_count", sa.Integer),
        sa.Column("peer_selection_method", sa.String(30)),
        sa.Column("multiples_comparison", JSONB),
        sa.Column("historical_avg_1y", JSONB),
        sa.Column("historical_avg_3y", JSONB),
        sa.Column("historical_avg_5y", JSONB),
        sa.Column("primary_multiple", sa.String(20)),
        sa.Column("composite_implied_price", sa.Numeric(18, 6)),
        sa.Column("current_price", sa.Numeric(18, 6)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_comps_security_date", "comps_results", ["security_id", "calculation_date"])

    # ── Composite Scores ──────────────────────────────────────────────
    op.create_table(
        "composite_scores",
        sa.Column("score_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("score_type", sa.String(30), nullable=False),
        sa.Column("score_value", sa.Numeric(6, 2)),
        sa.Column("classification", sa.String(30)),
        sa.Column("components", JSONB),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_composite_security_type",
        "composite_scores",
        ["security_id", "score_type", "calculation_date"],
    )


def downgrade() -> None:
    op.drop_table("composite_scores")
    op.drop_table("comps_results")
    op.drop_table("dcf_results")
