"""Market movers snapshot table.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_movers_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("sector", sa.String(50)),
        sa.Column("rankings", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_mm_date_category", "market_movers_snapshots", ["snapshot_date", "category"])


def downgrade() -> None:
    op.drop_table("market_movers_snapshots")
