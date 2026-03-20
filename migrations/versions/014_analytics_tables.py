"""Create Pillar 2 analytics engine tables.

Revision ID: 014
Revises: 013
Create Date: 2026-03-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Analytics Results ─────────────────────────────────────────────
    op.create_table(
        "analytics_results",
        sa.Column("result_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("engine_id", sa.String(10), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_category", sa.String(30), nullable=False),
        sa.Column("value", sa.Numeric(20, 6)),
        sa.Column("unit", sa.String(20), nullable=False, server_default="RATIO"),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_end_date", sa.Date()),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("inputs", JSONB()),
        sa.Column("calculation_version", sa.String(10), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ar_security_metric", "analytics_results", ["security_id", "metric_name", "period"])
    op.create_index("idx_ar_entity_metric", "analytics_results", ["entity_id", "metric_name"])
    op.create_index("idx_ar_category_date", "analytics_results", ["metric_category", "as_of_date"])

    # ── DuPont Decompositions ─────────────────────────────────────────
    op.create_table(
        "dupont_decompositions",
        sa.Column("decomposition_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_end_date", sa.Date()),
        sa.Column("model_type", sa.String(20), nullable=False),
        sa.Column("roe", sa.Numeric(12, 6)),
        sa.Column("net_profit_margin", sa.Numeric(12, 6)),
        sa.Column("asset_turnover", sa.Numeric(12, 6)),
        sa.Column("equity_multiplier", sa.Numeric(12, 6)),
        sa.Column("tax_burden", sa.Numeric(12, 6)),
        sa.Column("interest_burden", sa.Numeric(12, 6)),
        sa.Column("operating_margin", sa.Numeric(12, 6)),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("inputs", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_dupont_entity_period", "dupont_decompositions", ["entity_id", "period"])

    # ── Multiple Time Series ──────────────────────────────────────────
    op.create_table(
        "multiple_time_series",
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), primary_key=True),
        sa.Column("multiple_type", sa.String(30), primary_key=True),
        sa.Column("calculation_date", sa.Date(), primary_key=True),
        sa.Column("value", sa.Numeric(18, 6)),
        sa.Column("numerator_value", sa.Numeric(20, 2)),
        sa.Column("denominator_value", sa.Numeric(20, 2)),
        sa.Column("is_forward", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("forward_period", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_mts_security_type", "multiple_time_series", ["security_id", "multiple_type", "calculation_date"])

    # ── WACC Results ──────────────────────────────────────────────────
    op.create_table(
        "wacc_results",
        sa.Column("wacc_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("calculation_date", sa.Date(), nullable=False),
        sa.Column("risk_free_rate", sa.Numeric(8, 4)),
        sa.Column("equity_risk_premium", sa.Numeric(8, 4)),
        sa.Column("beta", sa.Numeric(6, 3)),
        sa.Column("size_premium", sa.Numeric(8, 4)),
        sa.Column("country_premium", sa.Numeric(8, 4)),
        sa.Column("cost_of_equity", sa.Numeric(8, 4)),
        sa.Column("cost_of_debt_pretax", sa.Numeric(8, 4)),
        sa.Column("effective_tax_rate", sa.Numeric(6, 4)),
        sa.Column("cost_of_debt_aftertax", sa.Numeric(8, 4)),
        sa.Column("debt_weight", sa.Numeric(6, 4)),
        sa.Column("equity_weight", sa.Numeric(6, 4)),
        sa.Column("wacc", sa.Numeric(8, 4)),
        sa.Column("market_cap", sa.Numeric(20, 2)),
        sa.Column("total_debt", sa.Numeric(20, 2)),
        sa.Column("assumptions", JSONB()),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_wacc_entity_date", "wacc_results", ["entity_id", "calculation_date"])

    # ── Calculation Lineage ───────────────────────────────────────────
    op.create_table(
        "calculation_lineage",
        sa.Column("lineage_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("engine_id", sa.String(10), nullable=False),
        sa.Column("engine_version", sa.String(20), nullable=False),
        sa.Column("output_metric", sa.String(100), nullable=False),
        sa.Column("output_value", sa.Numeric(20, 6)),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("calculation_formula", sa.Text()),
        sa.Column("inputs", JSONB(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_lineage_security_metric", "calculation_lineage", ["security_id", "output_metric", "period"])


def downgrade() -> None:
    op.drop_table("calculation_lineage")
    op.drop_table("wacc_results")
    op.drop_table("multiple_time_series")
    op.drop_table("dupont_decompositions")
    op.drop_table("analytics_results")
