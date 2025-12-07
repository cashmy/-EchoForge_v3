"""Add EF-02 transcription output columns.

Revision ID: 20251207_add_transcription_columns
Revises: 20251207_add_capture_fingerprint
Create Date: 2025-12-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251207_add_transcription_columns"
down_revision = "20251207_add_capture_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("verbatim_path", sa.Text(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("verbatim_preview", sa.Text(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("content_lang", sa.String(length=12), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("transcription_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column(
            "transcription_segments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "entries",
        sa.Column(
            "transcription_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "entries",
        sa.Column(
            "transcription_error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("entries", "transcription_error")
    op.drop_column("entries", "transcription_metadata")
    op.drop_column("entries", "transcription_segments")
    op.drop_column("entries", "transcription_text")
    op.drop_column("entries", "content_lang")
    op.drop_column("entries", "verbatim_preview")
    op.drop_column("entries", "verbatim_path")
