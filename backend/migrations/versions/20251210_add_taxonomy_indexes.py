"""Add indexes for taxonomy references.

Revision ID: 20251210_add_taxonomy_indexes
Revises: 20251210_add_taxonomy_columns
Create Date: 2025-12-10
"""

from __future__ import annotations

from alembic import op


revision = "20251210_add_taxonomy_indexes"
down_revision = "20251210_add_taxonomy_columns"
branch_labels = None
depends_on = None


_INDEX_DEFINITIONS = (
    ("IDX_entries_type_id", ["type_id"]),
    ("IDX_entries_domain_id", ["domain_id"]),
    ("IDX_entries_domain_type", ["domain_id", "type_id"]),
)


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name.lower() == "postgresql"


def _create_index(name: str, columns: list[str]) -> None:
    if _is_postgres():
        # Concurrent build avoids long-lived locks on large tables.
        with op.get_context().autocommit_block():
            op.create_index(
                name,
                "entries",
                columns,
                postgresql_concurrently=True,
            )
    else:
        op.create_index(name, "entries", columns)


def _drop_index(name: str) -> None:
    if _is_postgres():
        with op.get_context().autocommit_block():
            op.drop_index(name, table_name="entries", postgresql_concurrently=True)
    else:
        op.drop_index(name, table_name="entries")


def upgrade() -> None:
    for name, columns in _INDEX_DEFINITIONS:
        _create_index(name, columns)


def downgrade() -> None:
    # Drop in reverse order to avoid dependency surprises on composites.
    for name, _ in reversed(_INDEX_DEFINITIONS):
        _drop_index(name)
