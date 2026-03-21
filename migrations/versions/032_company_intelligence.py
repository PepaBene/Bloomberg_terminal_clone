"""Company intelligence and primer tables.

Revision ID: 032
Revises: 031
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_briefings",
        sa.Column("briefing_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("briefing_type", sa.String(20), nullable=False, server_default="DAILY"),
        sa.Column("briefing_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETED"),
        sa.Column("summary_text", sa.Text),
        sa.Column("key_signals", JSONB),
        sa.Column("valuation_context", JSONB),
        sa.Column("value_investing_lens", JSONB),
        sa.Column("data_snapshot", JSONB),
        sa.Column("ai_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_briefing_entity_id", "company_briefings", ["entity_id"])
    op.create_index(
        "idx_briefing_entity_type_date",
        "company_briefings",
        ["entity_id", "briefing_type", "briefing_date"],
        unique=True,
    )

    op.create_table(
        "company_primers",
        sa.Column("primer_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("generated_date", sa.Date, nullable=False),
        sa.Column("business_description", sa.Text),
        sa.Column("segments_breakdown", JSONB),
        sa.Column("competitive_position", sa.Text),
        sa.Column("financial_summary", JSONB),
        sa.Column("valuation_summary", JSONB),
        sa.Column("ownership_summary", JSONB),
        sa.Column("key_risks", JSONB),
        sa.Column("recent_developments", JSONB),
        sa.Column("ai_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_primer_entity_id", "company_primers", ["entity_id"])
    op.create_index(
        "idx_primer_entity_date",
        "company_primers",
        ["entity_id", "generated_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("company_primers")
    op.drop_table("company_briefings")
