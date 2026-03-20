"""Create data quality framework tables.

Revision ID: 004
Revises: 003
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- data_quality_scores ---
    op.create_table(
        "data_quality_scores",
        sa.Column("score_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(20), nullable=False, index=True),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("accuracy_score", sa.Numeric(5, 2)),
        sa.Column("completeness_score", sa.Numeric(5, 2)),
        sa.Column("timeliness_score", sa.Numeric(5, 2)),
        sa.Column("consistency_score", sa.Numeric(5, 2)),
        sa.Column("issues_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("critical_issues", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # --- data_quality_issues ---
    op.create_table(
        "data_quality_issues",
        sa.Column("issue_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(20), nullable=False, index=True),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("record_id", UUID(as_uuid=True)),
        sa.Column("issue_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, index=True),
        sa.Column("field_name", sa.String(100)),
        sa.Column("issue_description", sa.Text()),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("data_quality_issues")
    op.drop_table("data_quality_scores")
