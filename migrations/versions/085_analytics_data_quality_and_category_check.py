"""085 - Analytics results column-width and CHECK constraint reconciliation.

Covers two Pillar 2 model/migration drift items on `analytics_results`
(src/models/analytics.py vs. migrations/versions/014_analytics_tables.py):

  * Bug 68: model declares `data_quality: String(100)` but migration 014
    created it as VARCHAR(20). A 35+ char comma-joined flag string like
    "NO_DCF_DATA,NO_COMPS_DATA,NO_52W_DATA" fails/truncates on a database
    built from migrations alone.
  * Bug 55: model declares
    `CheckConstraint("metric_category = UPPER(metric_category)")` with no
    corresponding migration.

Revision ID: 085
Revises: 084
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "085"
down_revision: Union[str, None] = "084"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # -- Bug 68: data_quality VARCHAR(20) -> VARCHAR(100) --------------------
    op.alter_column(
        "analytics_results",
        "data_quality",
        type_=sa.String(100),
        existing_nullable=False,
    )

    # -- Bug 55: metric_category = UPPER(metric_category) CHECK --------------
    op.create_check_constraint(
        "ck_ar_metric_category_upper",
        "analytics_results",
        "metric_category = UPPER(metric_category)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ar_metric_category_upper", "analytics_results", type_="check")
    op.alter_column(
        "analytics_results",
        "data_quality",
        type_=sa.String(20),
        existing_nullable=False,
    )
