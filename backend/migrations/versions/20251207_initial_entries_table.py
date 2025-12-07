"""Create initial EF-06 entries table.

Revision ID: 20251207_initial_entries
Revises:
Create Date: 2025-12-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251207_initial_entries"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entries",
        sa.Column("entry_id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_channel", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column(
            "pipeline_status",
            sa.String(length=64),
            nullable=False,
            server_default="ingested",
        ),
        sa.Column(
            "cognitive_status",
            sa.String(length=64),
            nullable=False,
            server_default="unreviewed",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("entries")
