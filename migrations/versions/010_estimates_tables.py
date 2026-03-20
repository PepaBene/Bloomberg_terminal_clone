"""Create estimates tables (consensus, surprises, guidance).

Revision ID: 010
Revises: 009
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- consensus_estimates ---
    op.create_table(
        "consensus_estimates",
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), primary_key=True),
        sa.Column("metric", sa.String(30), primary_key=True),
        sa.Column("period_end_date", sa.Date(), primary_key=True),
        sa.Column("as_of_date", sa.Date(), primary_key=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("period_type", sa.String(20)),
        sa.Column("currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("mean", sa.Numeric(20, 4)),
        sa.Column("median", sa.Numeric(20, 4)),
        sa.Column("high", sa.Numeric(20, 4)),
        sa.Column("low", sa.Numeric(20, 4)),
        sa.Column("standard_deviation", sa.Numeric(20, 4)),
        sa.Column("num_estimates", sa.Integer()),
        sa.Column("num_revisions_up", sa.Integer()),
        sa.Column("num_revisions_down", sa.Integer()),
    )
    op.create_index("idx_consensus_security", "consensus_estimates", ["security_id"])
    op.create_index("idx_consensus_metric", "consensus_estimates", ["metric"])
    op.create_index("idx_consensus_period", "consensus_estimates", ["period_end_date"])

    # --- estimate_surprises ---
    op.create_table(
        "estimate_surprises",
        sa.Column("surprise_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("period_type", sa.String(20)),
        sa.Column("metric", sa.String(30), nullable=False),
        sa.Column("consensus_estimate", sa.Numeric(20, 4)),
        sa.Column("actual_value", sa.Numeric(20, 4)),
        sa.Column("surprise", sa.Numeric(20, 4)),
        sa.Column("surprise_percent", sa.Numeric(20, 4)),
        sa.Column("announcement_date", sa.Date(), index=True),
    )
    op.create_index("idx_surprise_security_metric", "estimate_surprises", ["security_id", "metric"])

    # --- company_guidance ---
    op.create_table(
        "company_guidance",
        sa.Column("guidance_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("period_type", sa.String(20)),
        sa.Column("metric", sa.String(30), nullable=False),
        sa.Column("guidance_type", sa.String(20)),
        sa.Column("point_estimate", sa.Numeric(20, 4)),
        sa.Column("low_estimate", sa.Numeric(20, 4)),
        sa.Column("high_estimate", sa.Numeric(20, 4)),
        sa.Column("currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("qualitative_guidance", sa.Text()),
        sa.Column("guidance_date", sa.Date()),
        sa.Column("source_event", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_guidance_entity_metric", "company_guidance", ["entity_id", "metric"])


def downgrade() -> None:
    op.drop_table("company_guidance")
    op.drop_table("estimate_surprises")
    op.drop_table("consensus_estimates")
