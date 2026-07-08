"""Pillar 3 Phase 2: Earnings call transcripts + earnings surprise/guidance extensions.

Revision ID: 048
Revises: 047
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- earnings_call_transcripts ---
    op.create_table(
        "earnings_call_transcripts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.UUID(),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("call_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=False),
        sa.Column("call_type", sa.String(20), server_default=sa.text("'EARNINGS'")),
        sa.Column("raw_text", sa.Text()),
        sa.Column("prepared_remarks", sa.Text()),
        sa.Column("qa_section", sa.Text()),
        sa.Column("ceo_section", sa.Text()),
        sa.Column("cfo_section", sa.Text()),
        sa.Column("participants", JSONB),
        sa.Column("overall_tone", sa.Numeric(5, 4)),
        sa.Column("prepared_tone", sa.Numeric(5, 4)),
        sa.Column("qa_tone", sa.Numeric(5, 4)),
        sa.Column("ceo_tone", sa.Numeric(5, 4)),
        sa.Column("cfo_tone", sa.Numeric(5, 4)),
        sa.Column("tone_divergence", sa.Numeric(5, 4)),
        sa.Column("tone_vs_prior_qtr", sa.Numeric(5, 4)),
        sa.Column("tone_vs_prior_year", sa.Numeric(5, 4)),
        sa.Column("hedging_ratio", sa.Numeric(5, 4)),
        sa.Column("confidence_ratio", sa.Numeric(5, 4)),
        sa.Column("forward_looking_pct", sa.Numeric(5, 4)),
        sa.Column("buzzword_counts", JSONB),
        sa.Column("mgmt_topics", JSONB),
        sa.Column("qa_topics", JSONB),
        sa.Column("absent_topics", JSONB),
        sa.Column("new_topics", JSONB),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("key_takeaways", JSONB),
        sa.Column("management_outlook", sa.String(20)),
        sa.Column("analyst_concerns", JSONB),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("source_type", sa.String(30)),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_transcript_entity", "earnings_call_transcripts", ["entity_id"])
    op.create_index(
        "uq_transcript_entity_period",
        "earnings_call_transcripts",
        ["entity_id", "fiscal_year", "fiscal_quarter"],
        unique=True,
    )
    op.create_index("idx_transcript_call_date", "earnings_call_transcripts", ["call_date"])

    # --- ALTER earnings_surprises: add Phase 2 columns ---
    op.add_column("earnings_surprises", sa.Column("ebitda_surprise", sa.Numeric(20, 2), nullable=True))
    op.add_column("earnings_surprises", sa.Column("ebitda_surprise_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column(
        "earnings_surprises",
        sa.Column("beat_and_fell", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("earnings_surprises", sa.Column("consecutive_beats", sa.Integer(), nullable=True))
    op.add_column("earnings_surprises", sa.Column("consecutive_misses", sa.Integer(), nullable=True))
    op.add_column(
        "earnings_surprises",
        sa.Column("avg_surprise_magnitude_4q", sa.Numeric(8, 4), nullable=True),
    )

    # --- ALTER guidance_tracking: add Phase 2 columns ---
    op.add_column("guidance_tracking", sa.Column("credibility_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("guidance_tracking", sa.Column("historical_accuracy", sa.Numeric(5, 4), nullable=True))
    op.add_column("guidance_tracking", sa.Column("consistency_score", sa.Numeric(5, 4), nullable=True))
    op.add_column("guidance_tracking", sa.Column("width_pct", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    # --- Revert guidance_tracking columns ---
    op.drop_column("guidance_tracking", "width_pct")
    op.drop_column("guidance_tracking", "consistency_score")
    op.drop_column("guidance_tracking", "historical_accuracy")
    op.drop_column("guidance_tracking", "credibility_score")

    # --- Revert earnings_surprises columns ---
    op.drop_column("earnings_surprises", "avg_surprise_magnitude_4q")
    op.drop_column("earnings_surprises", "consecutive_misses")
    op.drop_column("earnings_surprises", "consecutive_beats")
    op.drop_column("earnings_surprises", "beat_and_fell")
    op.drop_column("earnings_surprises", "ebitda_surprise_pct")
    op.drop_column("earnings_surprises", "ebitda_surprise")

    # --- Drop earnings_call_transcripts ---
    op.drop_table("earnings_call_transcripts")
