"""Create ESG & Sustainability tables.

Revision ID: 011
Revises: 010
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- esg_scores ---
    op.create_table(
        "esg_scores",
        sa.Column("score_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("esg_score", sa.Numeric(5, 2)),
        sa.Column("esg_percentile", sa.Numeric(5, 2)),
        sa.Column("esg_rating", sa.String(10)),
        sa.Column("environmental_score", sa.Numeric(5, 2)),
        sa.Column("social_score", sa.Numeric(5, 2)),
        sa.Column("governance_score", sa.Numeric(5, 2)),
        sa.Column("controversy_score", sa.Numeric(5, 2)),
        sa.Column("controversy_level", sa.String(10)),
        sa.Column("score_trend", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_esg_scores_entity", "esg_scores", ["entity_id"])
    op.create_index("idx_esg_scores_provider", "esg_scores", ["provider"])
    op.create_index(
        "uq_esg_score_entity_provider_date",
        "esg_scores",
        ["entity_id", "provider", "as_of_date"],
        unique=True,
    )

    # --- esg_metrics ---
    op.create_table(
        "esg_metrics",
        sa.Column("metric_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("metric_category", sa.String(20)),
        sa.Column("period_end_date", sa.Date()),
        sa.Column("period_type", sa.String(20)),
        sa.Column("value", sa.Numeric(20, 6)),
        sa.Column("unit", sa.String(50)),
        sa.Column("is_reported", sa.Boolean()),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_esg_metrics_entity", "esg_metrics", ["entity_id"])
    op.create_index("idx_esg_metrics_type", "esg_metrics", ["metric_type"])

    # --- esg_controversies ---
    op.create_table(
        "esg_controversies",
        sa.Column("controversy_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("controversy_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10)),
        sa.Column("description", sa.Text()),
        sa.Column("start_date", sa.Date()),
        sa.Column("resolution_date", sa.Date()),
        sa.Column("status", sa.String(20)),
        sa.Column("estimated_financial_impact", sa.Numeric(20, 2)),
        sa.Column("source", sa.String(50)),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_esg_controversies_entity", "esg_controversies", ["entity_id"])
    op.create_index("idx_esg_controversies_type", "esg_controversies", ["controversy_type"])


def downgrade() -> None:
    op.drop_table("esg_controversies")
    op.drop_table("esg_metrics")
    op.drop_table("esg_scores")
