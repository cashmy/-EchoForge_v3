"""Add taxonomy reference columns to entries.

Revision ID: 20251210_add_taxonomy_columns
Revises: 20251207_add_semantic_tags_column
Create Date: 2025-12-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251210_add_taxonomy_columns"
down_revision = "20251207_add_semantic_tags_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("type_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "entries",
        sa.Column("domain_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entries", "domain_id")
    op.drop_column("entries", "type_id")
