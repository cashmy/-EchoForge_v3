"""ETS safeguards for EF-06 taxonomy indexes."""

from __future__ import annotations

import os

import pytest

from scripts.taxonomy_harness import (
    DEFAULT_INDEXES,
    collect_explain_plans,
    fetch_index_scan_counts,
    get_connection,
    run_probe_queries,
    seed_taxonomy_entries,
)

pytestmark = [pytest.mark.ets_taxonomy, pytest.mark.ef06]

_DB_URL = os.getenv("ETS_TAXONOMY_DB_URL") or os.getenv("DATABASE_URL")
_db_skip = pytest.mark.skipif(
    not _DB_URL,
    reason="Set ETS_TAXONOMY_DB_URL or DATABASE_URL to run taxonomy DB ETS",
)


@_db_skip
def test_taxonomy_indexes_register_usage():
    """Seed data, run queries, and ensure target indexes are exercised."""

    with get_connection(db_url=_DB_URL) as conn:
        seed_taxonomy_entries(conn, total_rows=256)
        before_counts = fetch_index_scan_counts(conn)
        run_probe_queries(conn)
        plans = collect_explain_plans(conn)
        after_counts = fetch_index_scan_counts(conn)

    plan_lines = [line for lines in plans.values() for line in lines]
    for index_name in DEFAULT_INDEXES:
        assert any(index_name in line for line in plan_lines), (
            f"{index_name} missing from EXPLAIN ANALYZE output",
        )
        assert after_counts[index_name] >= before_counts[index_name], (
            f"{index_name} scan count regressed ({after_counts[index_name]} < {before_counts[index_name]})",
        )

    assert any(after_counts[name] > before_counts[name] for name in DEFAULT_INDEXES), (
        "At least one taxonomy index should register new scans"
    )
