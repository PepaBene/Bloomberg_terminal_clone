"""D11 FI Supplement P5: Credit rating analytics extension.

Revision ID: 038
Revises: 037
"""

import sqlalchemy as sa
from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade():
    # Extend credit_rating_events
    op.add_column("credit_rating_events", sa.Column("new_rating_numeric", sa.Integer()))
    op.add_column("credit_rating_events", sa.Column("old_rating_numeric", sa.Integer()))
    op.add_column("credit_rating_events", sa.Column("notches_changed", sa.Integer()))
    op.add_column("credit_rating_events", sa.Column("is_fallen_angel", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("credit_rating_events", sa.Column("is_rising_star", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("credit_rating_events", sa.Column("entity_stock_price_at_event", sa.Numeric(18, 6)))
    op.add_column("credit_rating_events", sa.Column("bond_spread_at_event", sa.Numeric(8, 2)))
    op.add_column("credit_rating_events", sa.Column("watch_status", sa.String(20)))

    # Create current_credit_ratings table
    op.create_table(
        "current_credit_ratings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("entity_id", sa.UUID(), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("agency", sa.String(10), nullable=False),
        sa.Column("rating_type", sa.String(20)),
        sa.Column("current_rating", sa.String(10), nullable=False),
        sa.Column("current_rating_numeric", sa.Integer()),
        sa.Column("outlook", sa.String(15)),
        sa.Column("watch_status", sa.String(20)),
        sa.Column("last_action_date", sa.Date()),
        sa.Column("last_action_type", sa.String(15)),
        sa.Column("is_investment_grade", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_current_rating_entity_agency",
        "current_credit_ratings",
        ["entity_id", "agency", "rating_type"],
        unique=True,
    )


def downgrade():
    op.drop_table("current_credit_ratings")
    for col in [
        "watch_status",
        "bond_spread_at_event",
        "entity_stock_price_at_event",
        "is_rising_star",
        "is_fallen_angel",
        "notches_changed",
        "old_rating_numeric",
        "new_rating_numeric",
    ]:
        op.drop_column("credit_rating_events", col)
