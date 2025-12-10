"""Print pg_stat_user_indexes rows for taxonomy indexes."""

from __future__ import annotations

from scripts.taxonomy_harness import fetch_index_scan_counts, get_connection


def main() -> None:
    with get_connection() as conn:
        stats = fetch_index_scan_counts(conn)

    for name, idx_scan in stats.items():
        print(f"{name}: {idx_scan}")


if __name__ == "__main__":
    main()
