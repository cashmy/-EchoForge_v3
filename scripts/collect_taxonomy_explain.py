"""Collect EXPLAIN ANALYZE output for taxonomy queries."""

from __future__ import annotations

from scripts.taxonomy_harness import collect_explain_plans, get_connection


def main() -> None:
    with get_connection() as conn:
        plans = collect_explain_plans(conn)

    for label, plan_lines in plans.items():
        print(f"\n--- {label} ---")
        for line in plan_lines:
            print(line)


if __name__ == "__main__":
    main()
