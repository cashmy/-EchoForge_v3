"""Shared helpers for taxonomy ETS harness + scripts."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Mapping, MutableMapping, Sequence

import psycopg
from psycopg import Connection
from psycopg.types.json import Json

DEFAULT_TYPES: Sequence[str] = (
    "type-alpha",
    "type-beta",
    "type-gamma",
    "type-delta",
)
DEFAULT_DOMAINS: Sequence[str] = (
    "domain-ops",
    "domain-research",
    "domain-ux",
    "domain-ai",
)
DEFAULT_INDEXES: Sequence[str] = (
    "IDX_entries_type_id",
    "IDX_entries_domain_id",
    "IDX_entries_domain_type",
)
DEFAULT_QUERIES: Mapping[str, str] = {
    "type_only": "SELECT entry_id FROM entries WHERE type_id = 'type-alpha' ORDER BY updated_at DESC LIMIT 25",
    "domain_only": "SELECT entry_id FROM entries WHERE domain_id = 'domain-ux' ORDER BY updated_at DESC LIMIT 25",
    "domain_type": "SELECT entry_id FROM entries WHERE domain_id = 'domain-ux' AND type_id = 'type-alpha' ORDER BY updated_at DESC LIMIT 25",
}


def resolve_db_url(db_url: str | None = None) -> str:
    """Return a Postgres URL, preferring ETS-specific env vars."""

    from_env = db_url or os.getenv("ETS_TAXONOMY_DB_URL") or os.getenv("DATABASE_URL")
    if not from_env:
        raise RuntimeError(
            "Set ETS_TAXONOMY_DB_URL or DATABASE_URL to run taxonomy DB helpers",
        )
    return from_env


def get_connection(*, db_url: str | None = None) -> Connection:
    """Create an autocommit psycopg connection."""

    resolved = resolve_db_url(db_url)
    conn = psycopg.connect(resolved)
    conn.autocommit = True
    return conn


def seed_taxonomy_entries(
    conn: Connection,
    *,
    total_rows: int = 2000,
    types: Sequence[str] = DEFAULT_TYPES,
    domains: Sequence[str] = DEFAULT_DOMAINS,
) -> int:
    """Insert synthetic entries for benchmarking; returns inserted row count."""

    combinations = max(1, len(types) * len(domains))
    per_combo = max(1, total_rows // combinations)
    cur = conn.cursor()
    inserted = 0
    now = datetime.now(timezone.utc)
    for type_id in types:
        for domain_id in domains:
            for _ in range(per_combo):
                entry_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO entries (
                        entry_id,
                        source_type,
                        source_channel,
                        pipeline_status,
                        cognitive_status,
                        metadata,
                        created_at,
                        updated_at,
                        transcription_metadata,
                        extraction_metadata,
                        type_id,
                        domain_id
                    ) VALUES (
                        %(entry_id)s,
                        %(source_type)s,
                        %(source_channel)s,
                        %(pipeline_status)s,
                        %(cognitive_status)s,
                        %(metadata)s,
                        %(created_at)s,
                        %(updated_at)s,
                        %(transcription_metadata)s,
                        %(extraction_metadata)s,
                        %(type_id)s,
                        %(domain_id)s
                    )
                    ON CONFLICT (entry_id) DO NOTHING
                    """,
                    {
                        "entry_id": entry_id,
                        "source_type": "document",
                        "source_channel": "bench_seed",
                        "pipeline_status": "normalized",
                        "cognitive_status": "unreviewed",
                        "created_at": now,
                        "updated_at": now,
                        "metadata": Json({}),
                        "transcription_metadata": Json({}),
                        "extraction_metadata": Json({}),
                        "type_id": type_id,
                        "domain_id": domain_id,
                    },
                )
                inserted += cur.rowcount
    cur.close()
    return inserted


def collect_explain_plans(
    conn: Connection,
    queries: Mapping[str, str] | None = None,
) -> dict[str, list[str]]:
    """Return EXPLAIN ANALYZE output for each query label."""

    compiled: dict[str, list[str]] = {}
    cur = conn.cursor()
    for label, sql in (queries or DEFAULT_QUERIES).items():
        cur.execute(f"EXPLAIN ANALYZE {sql}")
        compiled[label] = [row[0] for row in cur.fetchall()]
    cur.close()
    return compiled


def run_probe_queries(
    conn: Connection,
    queries: Mapping[str, str] | None = None,
) -> None:
    """Execute workload queries so Postgres records index usage."""

    cur = conn.cursor()
    for sql in (queries or DEFAULT_QUERIES).values():
        cur.execute(sql)
        cur.fetchall()
    cur.close()


def fetch_index_scan_counts(
    conn: Connection,
    indexes: Sequence[str] | None = None,
) -> MutableMapping[str, int]:
    """Return pg_stat_user_indexes scan counts keyed by index name."""

    target_indexes = tuple(indexes or DEFAULT_INDEXES)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT indexrelname, idx_scan
        FROM pg_stat_user_indexes
        WHERE indexrelname = ANY(%s)
        ORDER BY indexrelname
        """,
        (list(target_indexes),),
    )
    stats = {name: 0 for name in target_indexes}
    for name, idx_scan in cur.fetchall():
        stats[name] = idx_scan
    cur.close()
    return stats
