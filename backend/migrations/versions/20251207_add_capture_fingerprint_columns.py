"""Add capture fingerprint columns and supporting indexes.

Revision ID: 20251207_add_capture_fingerprint
Revises:
Create Date: 2025-12-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251207_add_capture_fingerprint"
down_revision = "20251207_initial_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("capture_fingerprint", sa.Text(), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("fingerprint_algo", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column(
            "capture_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "IDX_entries_fingerprint_channel",
        "entries",
        ["capture_fingerprint", "source_channel"],
        unique=True,
    )
    op.create_index(
        "IDX_entries_source_path",
        "entries",
        ["source_path"],
        unique=False,
    )
    op.create_index(
        "IDX_entries_source_channel",
        "entries",
        ["source_channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("IDX_entries_source_channel", table_name="entries")
    op.drop_index("IDX_entries_source_path", table_name="entries")
    op.drop_index("IDX_entries_fingerprint_channel", table_name="entries")
    op.drop_column("entries", "capture_metadata")
    op.drop_column("entries", "fingerprint_algo")
    op.drop_column("entries", "capture_fingerprint")
