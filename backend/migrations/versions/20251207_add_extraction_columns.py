"""Add EF-03 document extraction columns.

Revision ID: 20251207_add_extraction_columns
Revises: 20251207_add_transcription_columns
Create Date: 2025-12-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251207_add_extraction_columns"
down_revision = "20251207_add_transcription_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column(
            "extraction_segments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "entries",
        sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "entries",
        sa.Column(
            "extraction_error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("entries", "extraction_error")
    op.drop_column("entries", "extraction_metadata")
    op.drop_column("entries", "extraction_segments")
    op.drop_column("entries", "extracted_text")
