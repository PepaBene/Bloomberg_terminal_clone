"""Add source_url to geopolitical_events (Layer 2 §4.1 GDELT news bridge).

Revision ID: 097
Revises: 096
"""

import sqlalchemy as sa
from alembic import op

revision = "097"
down_revision = "096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("geopolitical_events", sa.Column("source_url", sa.String(1000)))
    op.create_index(
        "idx_geopolitical_events_source_url", "geopolitical_events", ["source_url"], unique=True
    )


def downgrade() -> None:
    op.drop_index("idx_geopolitical_events_source_url", table_name="geopolitical_events")
    op.drop_column("geopolitical_events", "source_url")
