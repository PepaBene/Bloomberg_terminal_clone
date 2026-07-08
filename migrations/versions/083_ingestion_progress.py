"""Ingestion progress tracking for resumable, rate-limited backfills.

Revision ID: 083
Revises: 082
"""

import sqlalchemy as sa
from alembic import op

revision = "083"
down_revision = "082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_progress",
        sa.Column("id", sa.UUID(), primary_key=True),
        # e.g. "xbrl", "corporate_actions", "esg", "prices"
        sa.Column("data_type", sa.String(40), nullable=False),
        # entity_id-as-text for entity-scoped types, or a date / ticker for others
        sa.Column("subject_key", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.UUID()),  # convenience for joins (nullable)
        # PENDING (retry), SUCCESS (has data), NO_DATA (gave up after retries)
        sa.Column("status", sa.String(15), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_ingested", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("data_type", "subject_key", name="uq_ingestion_progress_type_subject"),
    )
    op.create_index(
        "idx_ingestion_progress_type_status",
        "ingestion_progress",
        ["data_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_ingestion_progress_type_status", table_name="ingestion_progress")
    op.drop_table("ingestion_progress")
