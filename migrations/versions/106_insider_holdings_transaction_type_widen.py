"""095 - Widen insider_holdings.transaction_type VARCHAR(20) -> VARCHAR(30).

Same model/migration drift class as 085/093: the connector's
TRANSACTION_CODES vocabulary (src/ingestion/edgar_form4.py) includes values
like "DISPOSITION_TO_ISSUER" (21 chars) and "OPTION_EXERCISE_OOM" (20 chars,
exactly at the old limit), both wider than the VARCHAR(20) column created
originally. This only started surfacing once the shared SEC rate limiter
(src/ingestion/redis_rate_limiter.py) let Form 4 ingestion actually
complete enough real transactions to hit a DISPOSITION_TO_ISSUER row.

Revision ID: 106
Revises: 105
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "106"
down_revision: Union[str, None] = "105"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column(
        "insider_holdings", "transaction_type", type_=sa.String(30), existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "insider_holdings", "transaction_type", type_=sa.String(20), existing_nullable=True,
    )
