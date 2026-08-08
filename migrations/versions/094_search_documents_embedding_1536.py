"""Add search_documents.embedding_1536 (indexable RAG embedding) + HNSW index.

The existing `embedding` column (migration 087) stores gemini-embedding-002's
native 3072-dim output, which pgvector cannot index -- both HNSW and IVFFlat
cap out at 2000 dimensions. This adds a second column at a Gemini-native
reduced dimensionality (1536, requested via the embedding API's
output_dimensionality param -- not a client-side truncation) that the new
src/ai/retrieval/ stack embeds new chunks into and can actually build an ANN
index on. The legacy `embedding` (3072) and `embedding_vector` (JSONB)
columns are left untouched for the pre-existing brute-force vector_search.py
path.

Revision ID: 094
Revises: 093
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None

INDEXED_DIMENSIONS = 1536


def upgrade() -> None:
    op.add_column(
        "search_documents",
        sa.Column("embedding_1536", Vector(INDEXED_DIMENSIONS)),
    )
    op.execute(
        "CREATE INDEX idx_search_documents_embedding_1536_hnsw "
        "ON search_documents USING hnsw (embedding_1536 vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_search_documents_embedding_1536_hnsw")
    op.drop_column("search_documents", "embedding_1536")
