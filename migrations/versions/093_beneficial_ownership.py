"""Add beneficial_ownership_filings table (SEC Schedule 13D / 13G).

Revision ID: 093
Revises: 092
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beneficial_ownership_filings",
        sa.Column("filing_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "issuer_entity_id", UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"), nullable=False,
        ),
        sa.Column("security_id", UUID(as_uuid=True), sa.ForeignKey("securities.security_id")),
        sa.Column("filer_entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id")),
        sa.Column("filer_name", sa.String(300), nullable=False),
        sa.Column("filer_cik", sa.String(10)),
        sa.Column("reporting_person_type", sa.String(5)),
        sa.Column("schedule_type", sa.String(10), nullable=False),
        sa.Column("is_activist", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_amendment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("event_date", sa.Date()),
        sa.Column("shares_owned", sa.Numeric(20, 2)),
        sa.Column("percent_of_class", sa.Numeric(8, 4)),
        sa.Column("sole_voting_power", sa.Numeric(20, 2)),
        sa.Column("shared_voting_power", sa.Numeric(20, 2)),
        sa.Column("sole_dispositive_power", sa.Numeric(20, 2)),
        sa.Column("shared_dispositive_power", sa.Numeric(20, 2)),
        sa.Column("accession_number", sa.String(30)),
        sa.Column("filing_url", sa.String(500)),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Beneficial ownership disclosures from SEC Schedule 13D / 13G filings",
    )
    op.create_index(
        "idx_beneficial_ownership_issuer_date", "beneficial_ownership_filings",
        ["issuer_entity_id", "filing_date"],
    )
    op.create_index(
        "idx_beneficial_ownership_security", "beneficial_ownership_filings", ["security_id"],
    )
    op.create_index(
        "idx_beneficial_ownership_filer", "beneficial_ownership_filings", ["filer_entity_id"],
    )
    op.create_index(
        "idx_beneficial_ownership_schedule_type", "beneficial_ownership_filings", ["schedule_type"],
    )
    op.create_index(
        "uq_beneficial_ownership_accession", "beneficial_ownership_filings",
        ["accession_number"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_beneficial_ownership_accession", table_name="beneficial_ownership_filings")
    op.drop_index("idx_beneficial_ownership_schedule_type", table_name="beneficial_ownership_filings")
    op.drop_index("idx_beneficial_ownership_filer", table_name="beneficial_ownership_filings")
    op.drop_index("idx_beneficial_ownership_security", table_name="beneficial_ownership_filings")
    op.drop_index("idx_beneficial_ownership_issuer_date", table_name="beneficial_ownership_filings")
    op.drop_table("beneficial_ownership_filings")
