"""Pillar 4 Phase 4: Research Notes.

Revision ID: 080
Revises: 079
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "080"
down_revision = "079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_notes",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("note_type", sa.String(30), nullable=False, server_default="GENERAL"),
        sa.Column("entity_id", sa.String(50), index=True),
        sa.Column("portfolio_id", sa.UUID(), sa.ForeignKey("portfolios.id"), index=True),
        sa.Column("security_id", sa.String(50), index=True),
        sa.Column("ticker", sa.String(20)),
        sa.Column("tags", JSONB),
        sa.Column("sentiment", sa.String(10)),
        sa.Column("priority", sa.String(10), server_default="NORMAL"),
        sa.Column("is_pinned", sa.Boolean, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean, server_default=sa.text("false")),
        sa.Column("attachments", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Full-text search index on title and content
    op.execute(
        "CREATE INDEX ix_research_notes_search ON research_notes "
        "USING gin(to_tsvector('english', title || ' ' || content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_research_notes_search")
    op.drop_table("research_notes")
