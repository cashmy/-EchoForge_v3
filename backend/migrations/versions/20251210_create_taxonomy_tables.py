"""Create entry taxonomy tables.

Revision ID: 20251210_create_taxonomy_tables
Revises: 20251210_add_taxonomy_indexes
Create Date: 2025-12-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251210_create_taxonomy_tables"
down_revision = "20251210_add_taxonomy_indexes"
branch_labels = None
depends_on = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("500"),
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
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
    ]


def upgrade() -> None:
    op.create_table("entry_types", *_common_columns())
    op.create_index("IDX_entry_types_active", "entry_types", ["active"])
    op.create_index("IDX_entry_types_sort", "entry_types", ["sort_order", "label"])

    op.create_table("entry_domains", *_common_columns())
    op.create_index("IDX_entry_domains_active", "entry_domains", ["active"])
    op.create_index(
        "IDX_entry_domains_sort",
        "entry_domains",
        ["sort_order", "label"],
    )


def downgrade() -> None:
    op.drop_index("IDX_entry_domains_sort", table_name="entry_domains")
    op.drop_index("IDX_entry_domains_active", table_name="entry_domains")
    op.drop_table("entry_domains")

    op.drop_index("IDX_entry_types_sort", table_name="entry_types")
    op.drop_index("IDX_entry_types_active", table_name="entry_types")
    op.drop_table("entry_types")
