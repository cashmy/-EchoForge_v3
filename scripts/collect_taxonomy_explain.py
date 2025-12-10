"""Collect EXPLAIN ANALYZE output for taxonomy queries."""

from __future__ import annotations

import psycopg

DB_URL = "postgresql://postgres:LuckySebeka@localhost:5432/echo_forge"

QUERIES = {
    "type_only": "SELECT entry_id FROM entries WHERE type_id = 'type-alpha' ORDER BY created_at DESC LIMIT 25",
    "domain_only": "SELECT entry_id FROM entries WHERE domain_id = 'domain-ux' ORDER BY created_at DESC LIMIT 25",
    "domain_type": "SELECT entry_id FROM entries WHERE domain_id = 'domain-ux' AND type_id = 'type-alpha' ORDER BY created_at DESC LIMIT 25",
}


def main() -> None:
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()
    results: dict[str, list[str]] = {}
    for label, sql in QUERIES.items():
        cur.execute(f"EXPLAIN ANALYZE {sql}")
        rows = cur.fetchall()
        results[label] = [row[0] for row in rows]
    conn.close()

    for label, plan_lines in results.items():
        print(f"\n--- {label} ---")
        for line in plan_lines:
            print(line)


if __name__ == "__main__":
    main()
