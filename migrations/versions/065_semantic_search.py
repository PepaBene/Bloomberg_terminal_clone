"""Pillar 3 Phase 4B: Semantic search documents and query tracking.

Revision ID: 065
Revises: 064
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_type", sa.String(25), nullable=False),
        sa.Column("source_id", sa.String(100)),
        sa.Column("title", sa.String(500)),
        sa.Column("author", sa.String(200)),
        sa.Column("publish_date", sa.Date()),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=True, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_token_count", sa.Integer()),
        sa.Column("embedding_model", sa.String(50)),
        sa.Column("embedding_vector", JSONB),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "chunk_index"),
    )

    op.create_table(
        "search_queries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer()),
        sa.Column("execution_time_ms", sa.Integer()),
        sa.Column("top_result_relevance", sa.Numeric(3, 2)),
        sa.Column("ai_synthesis", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("search_queries")
    op.drop_table("search_documents")
