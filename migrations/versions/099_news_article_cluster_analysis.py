"""Add cluster_analysis JSONB column to news_articles (Layer 2 §4.4).

Populated only on a cluster's representative row (cluster_id == id) --
see src/ai/news/cluster_analyzer.py. Same shape/rationale as ai_analysis
(migration 098): one blob, no separate freshness/version check needed
since articles are immutable once enrichment has run.

Revision ID: 099
Revises: 098
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "099"
down_revision = "098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_articles", sa.Column("cluster_analysis", JSONB()))


def downgrade() -> None:
    op.drop_column("news_articles", "cluster_analysis")
