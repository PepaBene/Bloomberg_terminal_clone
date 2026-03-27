"""Pillar 3 Phase 4A: Company primer generation and refresh tracking.

Revision ID: 062
Revises: 061
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_primers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("primer_version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("executive_summary", sa.Text()),
        sa.Column("business_model", JSONB),
        sa.Column("competitive_landscape", JSONB),
        sa.Column("financial_health", JSONB),
        sa.Column("strategic_initiatives", JSONB),
        sa.Column("risk_factors", JSONB),
        sa.Column("analyst_consensus", JSONB),
        sa.Column("recent_catalysts", JSONB),
        sa.Column("data_completeness_score", sa.Numeric(5, 2)),
        sa.Column("last_filing_date", sa.Date()),
        sa.Column("last_earnings_call_date", sa.Date()),
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("prompt_template_used", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("entity_id", "primer_version", name="uq_primer_entity_version"),
    )

    op.create_table(
        "primer_refresh_log",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("refresh_type", sa.String(15), nullable=False),
        sa.Column("trigger_event", sa.String(50)),
        sa.Column("status", sa.String(15), server_default=sa.text("'PENDING'")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("primer_refresh_log")
    op.drop_table("company_primers")
