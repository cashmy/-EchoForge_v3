"""Seed synthetic entries for taxonomy index benchmarking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Json

DB_URL = "postgresql://postgres:LuckySebeka@localhost:5432/echo_forge"
TOTAL_ROWS = 2000
TYPES = ["type-alpha", "type-beta", "type-gamma", "type-delta"]
DOMAINS = ["domain-ops", "domain-research", "domain-ux", "domain-ai"]


def main() -> None:
    conn = psycopg.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    inserted = 0
    for type_id in TYPES:
        for domain_id in DOMAINS:
            for _ in range(TOTAL_ROWS // (len(TYPES) * len(DOMAINS))):
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
    print(f"Inserted {inserted} synthetic rows")
    conn.close()


if __name__ == "__main__":
    main()
