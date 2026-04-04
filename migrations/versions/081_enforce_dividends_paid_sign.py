"""Bug 26: Enforce dividends_paid sign convention (always <= 0).

Revision ID: 081
Revises: 080
"""

import sqlalchemy as sa
from alembic import op

revision = "081"
down_revision = "080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_cf_dividends_paid_negative",
        "cash_flow_statements",
        "dividends_paid <= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cf_dividends_paid_negative",
        "cash_flow_statements",
        type_="check",
    )
