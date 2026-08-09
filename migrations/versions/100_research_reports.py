"""Add research_reports table (Layer 2 — on-demand Deep Research, §4.6).

Revision ID: 100
Revises: 099
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "100"
down_revision = "099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(100)),
        sa.Column("subject_label", sa.String(500), nullable=False),
        sa.Column("focus", sa.Text()),
        sa.Column("sections", JSONB()),
        sa.Column("sources", JSONB()),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("model", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        comment="Layer 2 on-demand Deep Research reports (§4.6)",
    )
    op.create_index("idx_research_reports_subject", "research_reports", ["subject_type", "subject_id"])
    op.create_index("idx_research_reports_created_at", "research_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_research_reports_created_at", table_name="research_reports")
    op.drop_index("idx_research_reports_subject", table_name="research_reports")
    op.drop_table("research_reports")
