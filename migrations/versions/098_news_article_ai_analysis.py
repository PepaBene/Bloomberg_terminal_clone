"""Add ai_analysis JSONB column to news_articles (Layer 2 §4.4).

Revision ID: 098
Revises: 097
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "098"
down_revision = "097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_articles", sa.Column("ai_analysis", JSONB()))


def downgrade() -> None:
    op.drop_column("news_articles", "ai_analysis")
