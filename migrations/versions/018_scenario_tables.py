"""018 – Create scenario_results table for E8 Scenario & Sensitivity.

Revision ID: 018
Revises: 017
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "scenario_results",
        sa.Column("scenario_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id"), nullable=False, index=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("scenario_type", sa.String(30), nullable=False),
        sa.Column("scenario_name", sa.String(100), nullable=True),
        sa.Column("input_params", JSONB, nullable=False),
        sa.Column("output_data", JSONB, nullable=False),
        sa.Column("base_case_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("min_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("data_quality", sa.String(20), nullable=False, server_default="COMPLETE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_scenario_security_type",
        "scenario_results",
        ["security_id", "scenario_type", "calculation_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_scenario_security_type", table_name="scenario_results")
    op.drop_table("scenario_results")
