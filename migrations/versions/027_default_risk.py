"""Default risk scoring table.

Revision ID: 027
Revises: 026
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "default_risk_scores",
        sa.Column("score_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("calculation_date", sa.Date, nullable=False),
        # Altman
        sa.Column("altman_z_score", sa.Numeric(8, 4)),
        sa.Column("altman_zone", sa.String(20)),
        # Merton
        sa.Column("merton_dd", sa.Numeric(8, 4)),
        sa.Column("merton_pd", sa.Numeric(10, 8)),
        sa.Column("merton_asset_value", sa.Numeric(20, 2)),
        sa.Column("merton_asset_vol", sa.Numeric(8, 6)),
        sa.Column("equity_volatility", sa.Numeric(8, 6)),
        # Composite
        sa.Column("composite_score", sa.Numeric(5, 1)),
        sa.Column("implied_rating", sa.String(5)),
        sa.Column("credit_zone", sa.String(20)),
        sa.Column("key_drivers", JSONB),
        # Trend
        sa.Column("prior_score", sa.Numeric(5, 1)),
        sa.Column("score_change", sa.Numeric(5, 1)),
        sa.Column("trend", sa.String(20)),
        # Meta
        sa.Column("data_quality", sa.String(20)),
        sa.Column("inputs", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_drs_entity_date", "default_risk_scores", ["entity_id", "calculation_date"])
    op.create_index("idx_drs_composite", "default_risk_scores", ["composite_score"])


def downgrade() -> None:
    op.drop_table("default_risk_scores")
