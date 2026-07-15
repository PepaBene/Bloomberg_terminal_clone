"""Pillar 3 models/schemas reconciliation (M-001, M-002, M-003, M-006-M-011,
M-013, M-015).

`src/models/*.py` had been edited to address nearly every item in the
Pillar-3 "Models & schemas" audit section, but none of those edits were
ever backed by a migration -- migrations 033/043/047/064/065/066/070 still
create the original, narrower/uncascaded/unindexed schema. This migration
reconciles the two so a database built from `alembic upgrade head` actually
matches what the ORM models declare.

- M-001: enable pgvector, add `search_documents.embedding` (real VECTOR
  column + HNSW cosine index), backfill from the legacy JSONB
  `embedding_vector` column.
- M-002: widen narrow VARCHAR columns (source_type, section_key,
  anomaly_type) to match the model.
- M-003: `thesis_versions.thesis_id` FK gets ON DELETE CASCADE.
- M-006: `consolidated_alerts.updated_at`.
- M-007: `search_documents.updated_at`, `search_queries.updated_at`.
- M-008: `thesis_versions.updated_at`.
- M-009: `sentiment_aggregates` DESC index on `as_of_date`.
- M-010: `search_documents` (source_type, source_id) index.
- M-011: ON DELETE CASCADE on the 5 entity_id FKs (SentimentScore,
  SentimentAggregate, FilingSection, FilingDiff, ArticleEntityLink).
- M-013: `news_articles.summary` NOT NULL (existing NULLs backfilled to
  '' first so the ALTER doesn't fail on real data).
- M-015: unique index on SentimentScore(entity_id, source_type,
  source_reference).

Revision ID: 087
Revises: 086
"""

import sqlalchemy as sa
from alembic import op

revision = "087"
down_revision = "086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── M-001: pgvector ──────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Vector isn't a core SQLAlchemy type, so the column is added via raw
    # DDL rather than op.add_column(sa.Column(...)).
    op.execute("ALTER TABLE search_documents ADD COLUMN embedding vector(3072)")
    # Backfill from the legacy JSONB column so documents indexed before
    # this migration aren't silently dropped from vector search.
    op.execute(
        """
        UPDATE search_documents
        SET embedding = (
            SELECT array_agg(elem::float8)::vector
            FROM jsonb_array_elements_text(embedding_vector) AS elem
        )
        WHERE embedding_vector IS NOT NULL
          AND jsonb_typeof(embedding_vector) = 'array'
        """
    )
    op.execute(
        "CREATE INDEX idx_search_documents_embedding_hnsw "
        "ON search_documents USING hnsw (embedding vector_cosine_ops)"
    )

    # ── M-002: widen narrow VARCHAR columns ─────────────────────────
    op.alter_column("sentiment_scores", "source_type", type_=sa.String(50))
    op.alter_column("search_documents", "source_type", type_=sa.String(50))
    op.alter_column("filing_sections", "section_key", type_=sa.String(60))
    op.alter_column("filing_diffs", "section_key", type_=sa.String(60))
    op.alter_column("detected_anomalies", "anomaly_type", type_=sa.String(60))
    op.alter_column("anomaly_rules", "anomaly_type", type_=sa.String(60))

    # ── M-003 / M-011: ON DELETE CASCADE on unnamed FKs ─────────────
    # These were created via inline `sa.ForeignKey(...)` with no explicit
    # constraint name, so Postgres assigned its default `<table>_<col>_fkey`.
    cascade_fks = [
        ("sentiment_scores_entity_id_fkey", "sentiment_scores", "entity_id", "entities", "entity_id"),
        ("sentiment_aggregates_entity_id_fkey", "sentiment_aggregates", "entity_id", "entities", "entity_id"),
        ("filing_sections_entity_id_fkey", "filing_sections", "entity_id", "entities", "entity_id"),
        ("filing_diffs_entity_id_fkey", "filing_diffs", "entity_id", "entities", "entity_id"),
        ("article_entity_links_entity_id_fkey", "article_entity_links", "entity_id", "entities", "entity_id"),
        ("thesis_versions_thesis_id_fkey", "thesis_versions", "thesis_id", "investment_theses", "id"),
    ]
    for fk_name, table, col, ref_table, ref_col in cascade_fks:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(fk_name, table, ref_table, [col], [ref_col], ondelete="CASCADE")

    # ── M-006/M-007/M-008: updated_at columns ───────────────────────
    op.add_column(
        "consolidated_alerts",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.add_column(
        "search_documents",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.add_column(
        "search_queries",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.add_column(
        "thesis_versions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── M-009: SentimentAggregate DESC index ────────────────────────
    op.execute(
        "CREATE INDEX ix_sentiment_agg_entity_date "
        "ON sentiment_aggregates (entity_id, as_of_date DESC)"
    )

    # ── M-010: SearchDocument source index ──────────────────────────
    op.create_index(
        "idx_search_documents_source", "search_documents", ["source_type", "source_id"]
    )

    # ── M-013: NewsArticle.summary NOT NULL ─────────────────────────
    op.execute("UPDATE news_articles SET summary = '' WHERE summary IS NULL")
    op.alter_column("news_articles", "summary", nullable=False)

    # ── M-015: SentimentScore unique constraint ─────────────────────
    op.create_index(
        "uq_sentiment_entity_source",
        "sentiment_scores",
        ["entity_id", "source_type", "source_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_sentiment_entity_source", table_name="sentiment_scores")
    op.alter_column("news_articles", "summary", nullable=True)
    op.drop_index("idx_search_documents_source", table_name="search_documents")
    op.execute("DROP INDEX IF EXISTS ix_sentiment_agg_entity_date")
    op.drop_column("thesis_versions", "updated_at")
    op.drop_column("search_queries", "updated_at")
    op.drop_column("search_documents", "updated_at")
    op.drop_column("consolidated_alerts", "updated_at")

    for fk_name, table, col, ref_table, ref_col in [
        ("thesis_versions_thesis_id_fkey", "thesis_versions", "thesis_id", "investment_theses", "id"),
        ("article_entity_links_entity_id_fkey", "article_entity_links", "entity_id", "entities", "entity_id"),
        ("filing_diffs_entity_id_fkey", "filing_diffs", "entity_id", "entities", "entity_id"),
        ("filing_sections_entity_id_fkey", "filing_sections", "entity_id", "entities", "entity_id"),
        ("sentiment_aggregates_entity_id_fkey", "sentiment_aggregates", "entity_id", "entities", "entity_id"),
        ("sentiment_scores_entity_id_fkey", "sentiment_scores", "entity_id", "entities", "entity_id"),
    ]:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(fk_name, table, ref_table, [col], [ref_col])

    op.alter_column("anomaly_rules", "anomaly_type", type_=sa.String(25))
    op.alter_column("detected_anomalies", "anomaly_type", type_=sa.String(25))
    op.alter_column("filing_diffs", "section_key", type_=sa.String(20))
    op.alter_column("filing_sections", "section_key", type_=sa.String(20))
    op.alter_column("search_documents", "source_type", type_=sa.String(25))
    op.alter_column("sentiment_scores", "source_type", type_=sa.String(20))

    op.execute("DROP INDEX IF EXISTS idx_search_documents_embedding_hnsw")
    op.drop_column("search_documents", "embedding")
