"""Pillar 3 Phase 2: Deep company intelligence tables.

Revision ID: 052
Revises: 051
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- business_model_analyses ---
    op.create_table(
        "business_model_analyses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("revenue_decomposition", JSONB),
        sa.Column("recurring_pct", sa.Numeric(5, 2)),
        sa.Column("deferred_revenue_trend", sa.String(15)),
        sa.Column("customer_concentration", sa.Numeric(5, 2)),
        sa.Column("diversification_score", sa.Numeric(5, 2)),
        sa.Column("cyclicality_score", sa.Numeric(5, 2)),
        sa.Column("revenue_per_employee", sa.Numeric(20, 2)),
        sa.Column("unit_economics", JSONB),
        sa.Column("operating_leverage", sa.Numeric(8, 4)),
        sa.Column("incremental_margin", sa.Numeric(8, 4)),
        sa.Column("sga_scalability", sa.Numeric(8, 4)),
        sa.Column("switching_cost_score", sa.Numeric(5, 2)),
        sa.Column("moat_type", sa.String(30)),
        sa.Column("disruption_vulnerability", sa.Numeric(5, 2)),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bma_entity", "business_model_analyses", ["entity_id"])
    op.create_index("idx_bma_entity_date", "business_model_analyses", ["entity_id", "as_of_date"])

    # --- capital_allocation_assessments ---
    op.create_table(
        "capital_allocation_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("ebitda_to_fcf_conversion", sa.Numeric(8, 4)),
        sa.Column("maintenance_capex_pct", sa.Numeric(8, 4)),
        sa.Column("growth_capex_pct", sa.Numeric(8, 4)),
        sa.Column("working_capital_discipline", JSONB),
        sa.Column("roic_vs_wacc_spread", sa.Numeric(8, 4)),
        sa.Column("roic_vs_wacc_history", JSONB),
        sa.Column("ma_discipline", JSONB),
        sa.Column("buyback_effectiveness", JSONB),
        sa.Column("dividend_sustainability", JSONB),
        sa.Column("overall_score", sa.Numeric(5, 2)),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_caa_entity", "capital_allocation_assessments", ["entity_id"])
    op.create_index(
        "idx_caa_entity_date",
        "capital_allocation_assessments",
        ["entity_id", "as_of_date"],
    )

    # --- balance_sheet_risk_assessments ---
    op.create_table(
        "balance_sheet_risk_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("net_debt_ebitda", sa.Numeric(8, 4)),
        sa.Column("net_debt_ebitda_trend", sa.String(15)),
        sa.Column("interest_coverage", sa.Numeric(8, 4)),
        sa.Column("interest_coverage_trend", sa.String(15)),
        sa.Column("liquidity_ratio", sa.Numeric(8, 4)),
        sa.Column("cash_burn_rate", sa.Numeric(20, 2)),
        sa.Column("refinancing_risk_score", sa.Numeric(5, 2)),
        sa.Column("maturity_24mo_pct", sa.Numeric(8, 4)),
        sa.Column("coverage_trend", sa.String(15)),
        sa.Column("z_score", sa.Numeric(8, 4)),
        sa.Column("covenant_analysis", JSONB),
        sa.Column("fi_profile", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bsra_entity", "balance_sheet_risk_assessments", ["entity_id"])
    op.create_index(
        "idx_bsra_entity_date",
        "balance_sheet_risk_assessments",
        ["entity_id", "as_of_date"],
    )

    # --- management_quality_assessments ---
    op.create_table(
        "management_quality_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("guidance_accuracy_score", sa.Numeric(5, 2)),
        sa.Column("strategic_consistency_score", sa.Numeric(5, 2)),
        sa.Column("margin_stability_score", sa.Numeric(5, 2)),
        sa.Column("wc_management_score", sa.Numeric(5, 2)),
        sa.Column("execution_score", sa.Numeric(5, 2)),
        sa.Column("beneish_m_score", sa.Numeric(8, 4)),
        sa.Column("accruals_quality", sa.Numeric(8, 4)),
        sa.Column("auditor_change_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("restatement_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("compensation_alignment", JSONB),
        sa.Column("governance_score", sa.Numeric(5, 2)),
        sa.Column("overall_quality_score", sa.Numeric(5, 2)),
        sa.Column("red_flags", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mqa_entity", "management_quality_assessments", ["entity_id"])
    op.create_index(
        "idx_mqa_entity_date",
        "management_quality_assessments",
        ["entity_id", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_table("management_quality_assessments")
    op.drop_table("balance_sheet_risk_assessments")
    op.drop_table("capital_allocation_assessments")
    op.drop_table("business_model_analyses")
