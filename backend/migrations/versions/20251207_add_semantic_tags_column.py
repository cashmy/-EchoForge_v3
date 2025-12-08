"""Add EF-05 semantic tags column.

Revision ID: 20251207_add_semantic_tags_column
Revises: 20251207_add_extraction_columns
Create Date: 2025-12-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251207_add_semantic_tags_column"
down_revision = "20251207_add_extraction_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column(
            "semantic_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("entries", "semantic_tags")
