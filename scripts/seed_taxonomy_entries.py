"""Seed synthetic entries for taxonomy index benchmarking."""

from __future__ import annotations

from scripts.taxonomy_harness import get_connection, seed_taxonomy_entries

TOTAL_ROWS = 2000


def main() -> None:
    with get_connection() as conn:
        inserted = seed_taxonomy_entries(conn, total_rows=TOTAL_ROWS)
    print(f"Inserted {inserted} synthetic rows")


if __name__ == "__main__":
    main()
