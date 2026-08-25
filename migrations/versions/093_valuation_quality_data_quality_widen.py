"""093 - Widen data_quality on dcf_results/comps_results/composite_scores.

Same model/migration drift class as 085 (which fixed analytics_results):
migration 015 created these three columns as VARCHAR(20), but the models
(src/models/analytics.py) declare String(100). The DCF engine writes
comma-joined flag strings like "HIGH_TERMINAL_DEPENDENCY" (25 chars) into
dcf_results.data_quality, which fails with StringDataRightTruncationError
on a database built from migrations alone.

Revision ID: 093
Revises: 092
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "093"
down_revision: Union[str, None] = "092"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column(
        "dcf_results", "data_quality", type_=sa.String(100), existing_nullable=False,
    )
    op.alter_column(
        "comps_results", "data_quality", type_=sa.String(100), existing_nullable=False,
    )
    op.alter_column(
        "composite_scores", "data_quality", type_=sa.String(100), existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "composite_scores", "data_quality", type_=sa.String(20), existing_nullable=False,
    )
    op.alter_column(
        "comps_results", "data_quality", type_=sa.String(20), existing_nullable=False,
    )
    op.alter_column(
        "dcf_results", "data_quality", type_=sa.String(20), existing_nullable=False,
    )
