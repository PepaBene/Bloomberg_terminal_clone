"""Pillar 3 Phase 1: Filing sections and year-over-year diffs.

Revision ID: 043
Revises: 042
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- filing_sections ---
    op.create_table(
        "filing_sections",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("filing_type", sa.String(10), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("section_key", sa.String(20), nullable=False),
        sa.Column("section_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("filing_accession_number", sa.String(25)),
        sa.Column("filing_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_filing_section",
        "filing_sections",
        ["entity_id", "filing_type", "fiscal_year", "section_key"],
        unique=True,
    )
    op.create_index(
        "idx_filing_section_entity_year",
        "filing_sections",
        ["entity_id", "fiscal_year"],
    )

    # --- filing_diffs ---
    op.create_table(
        "filing_diffs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(20), nullable=False),
        sa.Column("year_old", sa.Integer(), nullable=False),
        sa.Column("year_new", sa.Integer(), nullable=False),
        sa.Column("change_pct", sa.Numeric(5, 2)),
        sa.Column("change_classification", sa.String(20)),
        sa.Column("substantive_change_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("boilerplate_change_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("numerical_change_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("structural_change_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("added_paragraphs", JSONB),
        sa.Column("removed_paragraphs", JSONB),
        sa.Column("modified_paragraphs", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("materiality", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_filing_diff",
        "filing_diffs",
        ["entity_id", "section_key", "year_old", "year_new"],
        unique=True,
    )
    op.create_index(
        "idx_filing_diff_entity_year",
        "filing_diffs",
        ["entity_id", "year_new"],
    )


def downgrade() -> None:
    op.drop_table("filing_diffs")
    op.drop_table("filing_sections")
