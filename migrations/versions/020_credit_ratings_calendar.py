"""020 – Credit rating events & calendar events (Pillar 1 Supplement §4, §8).

Revision ID: 020
Revises: 019
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # -- Credit Rating Events ------------------------------------------------
    op.create_table(
        "credit_rating_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False, index=True),
        sa.Column("agency", sa.String(10), nullable=False),
        sa.Column("rating_type", sa.String(20), nullable=True),
        sa.Column("new_rating", sa.String(10), nullable=True),
        sa.Column("old_rating", sa.String(10), nullable=True),
        sa.Column("direction", sa.String(15), nullable=True),
        sa.Column("outlook", sa.String(15), nullable=True),
        sa.Column("event_date", sa.Date, nullable=False, index=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_filing_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rating_entity_date", "credit_rating_events", ["entity_id", "event_date"])
    op.create_index("idx_rating_agency", "credit_rating_events", ["agency"])

    # -- Calendar Events -----------------------------------------------------
    op.create_table(
        "calendar_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=True, index=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("event_date", sa.Date, nullable=False, index=True),
        sa.Column("event_description", sa.Text, nullable=True),
        sa.Column("corporate_action_id", UUID(as_uuid=True), sa.ForeignKey("corporate_actions.action_id"), nullable=True),
        sa.Column("deal_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ipo_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_calendar_date_type", "calendar_events", ["event_date", "event_type"])
    op.create_index("idx_calendar_entity_date", "calendar_events", ["entity_id", "event_date"])


def downgrade() -> None:
    op.drop_index("idx_calendar_entity_date", table_name="calendar_events")
    op.drop_index("idx_calendar_date_type", table_name="calendar_events")
    op.drop_table("calendar_events")
    op.drop_index("idx_rating_agency", table_name="credit_rating_events")
    op.drop_index("idx_rating_entity_date", table_name="credit_rating_events")
    op.drop_table("credit_rating_events")
