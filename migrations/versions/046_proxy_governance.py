"""Pillar 3 Phase 1: Proxy filings, exec comp, board, proposals, governance.

Revision ID: 046
Revises: 045
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- proxy_filings ---
    op.create_table(
        "proxy_filings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("meeting_date", sa.Date()),
        sa.Column("filing_accession_number", sa.String(25)),
        sa.Column("filing_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_proxy_entity_year",
        "proxy_filings",
        ["entity_id", "fiscal_year"],
        unique=True,
    )

    # --- executive_compensation ---
    op.create_table(
        "executive_compensation",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "proxy_id",
            sa.UUID(),
            sa.ForeignKey("proxy_filings.id"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("person_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("total_compensation", sa.Numeric(15, 2)),
        sa.Column("base_salary", sa.Numeric(12, 2)),
        sa.Column("bonus", sa.Numeric(12, 2)),
        sa.Column("stock_awards", sa.Numeric(12, 2)),
        sa.Column("option_awards", sa.Numeric(12, 2)),
        sa.Column("non_equity_incentive", sa.Numeric(12, 2)),
        sa.Column("other_compensation", sa.Numeric(12, 2)),
        sa.Column("change_in_pension", sa.Numeric(12, 2)),
        sa.Column("yoy_change_pct", sa.Numeric(8, 4)),
        sa.Column("pay_ratio_to_median", sa.Numeric(10, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_exec_comp",
        "executive_compensation",
        ["entity_id", "person_name", "fiscal_year"],
        unique=True,
    )

    # --- board_members ---
    op.create_table(
        "board_members",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "proxy_id",
            sa.UUID(),
            sa.ForeignKey("proxy_filings.id"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("person_name", sa.String(200), nullable=False),
        sa.Column("is_independent", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_chair", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tenure_years", sa.Integer()),
        sa.Column("age", sa.Integer()),
        sa.Column("gender", sa.String(10)),
        sa.Column("committees", JSONB),
        sa.Column("expertise_areas", JSONB),
        sa.Column("other_boards", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_board_member",
        "board_members",
        ["entity_id", "person_name", "proxy_id"],
        unique=True,
    )

    # --- shareholder_proposals ---
    op.create_table(
        "shareholder_proposals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "proxy_id",
            sa.UUID(),
            sa.ForeignKey("proxy_filings.id"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("proposal_number", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(30)),
        sa.Column("description", sa.Text()),
        sa.Column("proponent", sa.String(200)),
        sa.Column("management_recommendation", sa.String(10)),
        sa.Column("vote_for_pct", sa.Numeric(5, 2)),
        sa.Column("vote_against_pct", sa.Numeric(5, 2)),
        sa.Column("vote_abstain_pct", sa.Numeric(5, 2)),
        sa.Column("passed", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- governance_assessments ---
    op.create_table(
        "governance_assessments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("governance_score", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("classification", sa.String(20)),
        sa.Column("dual_class", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ceo_is_chair", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("board_independence_pct", sa.Numeric(5, 2)),
        sa.Column("avg_board_tenure", sa.Numeric(4, 1)),
        sa.Column("has_poison_pill", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_staggered_board", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_majority_voting", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("related_party_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ceo_pay_ratio", sa.Numeric(10, 2)),
        sa.Column("long_term_incentive_pct", sa.Numeric(5, 2)),
        sa.Column("board_diversity_pct", sa.Numeric(5, 2)),
        sa.Column("board_interlock_count", sa.Integer()),
        sa.Column("red_flags", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_governance_entity_date",
        "governance_assessments",
        ["entity_id", "assessment_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("governance_assessments")
    op.drop_table("shareholder_proposals")
    op.drop_table("board_members")
    op.drop_table("executive_compensation")
    op.drop_table("proxy_filings")
