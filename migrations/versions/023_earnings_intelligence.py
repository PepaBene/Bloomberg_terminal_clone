"""Earnings surprises and guidance tracking.

Revision ID: 023
Revises: 022
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # earnings_surprises
    op.create_table(
        "earnings_surprises",
        sa.Column("surprise_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=False),
        sa.Column("period_end_date", sa.Date()),
        sa.Column("actual_eps", sa.Numeric(12, 4)),
        sa.Column("actual_revenue", sa.Numeric(20, 2)),
        sa.Column("actual_ebitda", sa.Numeric(20, 2)),
        sa.Column("consensus_eps", sa.Numeric(12, 4)),
        sa.Column("consensus_revenue", sa.Numeric(20, 2)),
        sa.Column("consensus_ebitda", sa.Numeric(20, 2)),
        sa.Column("number_of_estimates", sa.Integer()),
        sa.Column("eps_surprise", sa.Numeric(12, 4)),
        sa.Column("eps_surprise_pct", sa.Numeric(8, 4)),
        sa.Column("revenue_surprise", sa.Numeric(20, 2)),
        sa.Column("revenue_surprise_pct", sa.Numeric(8, 4)),
        sa.Column("announcement_date", sa.Date()),
        sa.Column("pre_earnings_close", sa.Numeric(12, 4)),
        sa.Column("post_earnings_close", sa.Numeric(12, 4)),
        sa.Column("price_reaction_pct", sa.Numeric(8, 4)),
        sa.Column("price_reaction_5d_pct", sa.Numeric(8, 4)),
        sa.Column("source_filing_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_surprise_entity", "earnings_surprises", ["entity_id"])
    op.create_index("idx_surprise_entity_period", "earnings_surprises", ["entity_id", "fiscal_year", "fiscal_quarter"])
    op.create_index("idx_surprise_announcement", "earnings_surprises", ["announcement_date"])

    # guidance_tracking
    op.create_table(
        "guidance_tracking",
        sa.Column("guidance_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("guidance_fiscal_year", sa.Integer(), nullable=False),
        sa.Column("guidance_fiscal_quarter", sa.Integer()),
        sa.Column("metric", sa.String(20), nullable=False),
        sa.Column("guidance_low", sa.Numeric(20, 4)),
        sa.Column("guidance_high", sa.Numeric(20, 4)),
        sa.Column("guidance_midpoint", sa.Numeric(20, 4)),
        sa.Column("guidance_date", sa.Date(), nullable=False),
        sa.Column("guidance_type", sa.String(15)),
        sa.Column("prior_guidance_low", sa.Numeric(20, 4)),
        sa.Column("prior_guidance_high", sa.Numeric(20, 4)),
        sa.Column("consensus_at_guidance_date", sa.Numeric(20, 4)),
        sa.Column("guidance_vs_consensus", sa.String(10)),
        sa.Column("source_filing_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_guidance_entity", "guidance_tracking", ["entity_id"])
    op.create_index("idx_guidance_entity_year", "guidance_tracking", ["entity_id", "guidance_fiscal_year"])
    op.create_index("idx_guidance_date", "guidance_tracking", ["guidance_date"])


def downgrade() -> None:
    op.drop_index("idx_guidance_date", table_name="guidance_tracking")
    op.drop_index("idx_guidance_entity_year", table_name="guidance_tracking")
    op.drop_index("idx_guidance_entity", table_name="guidance_tracking")
    op.drop_table("guidance_tracking")
    op.drop_index("idx_surprise_announcement", table_name="earnings_surprises")
    op.drop_index("idx_surprise_entity_period", table_name="earnings_surprises")
    op.drop_index("idx_surprise_entity", table_name="earnings_surprises")
    op.drop_table("earnings_surprises")
