"""Seed script for EF-06 Entries table.

Creates a handful of sample Entries so local UIs and API calls have
data to read without running the full ingestion pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.config import load_settings


def build_seed_entries(timestamp: datetime) -> List[dict[str, object]]:
    """Return static seed data for EF-06 entries."""

    return [
        {
            "entry_id": "00000000-0000-0000-0000-000000000001",
            "source_type": "audio",
            "source_channel": "watch_folder_audio",
            "source_path": "watch_roots/audio/processed/demo_meeting.wav",
            "pipeline_status": "queued_for_transcription",
            "cognitive_status": "unreviewed",
            "metadata": {
                "title": "Quarterly planning meeting",
                "seed": True,
                "duration_seconds": 1320,
            },
            "capture_fingerprint": "seed-audio-sha256",
            "fingerprint_algo": "sha256:path+size",
            "capture_metadata": {
                "watch_root_id": "dev-audio",
                "note": "Seeded via scripts/seed_db.py",
            },
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        {
            "entry_id": "00000000-0000-0000-0000-000000000002",
            "source_type": "document",
            "source_channel": "watch_folder_document",
            "source_path": "watch_roots/documents/processed/market_research.pdf",
            "pipeline_status": "queued_for_extraction",
            "cognitive_status": "unreviewed",
            "metadata": {
                "title": "Market research digest",
                "seed": True,
                "pages": 18,
            },
            "capture_fingerprint": "seed-doc-sha256",
            "fingerprint_algo": "sha256:path+size",
            "capture_metadata": {
                "watch_root_id": "dev-documents",
                "note": "Seeded via scripts/seed_db.py",
            },
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        {
            "entry_id": "00000000-0000-0000-0000-000000000003",
            "source_type": "text",
            "source_channel": "manual_text",
            "source_path": None,
            "pipeline_status": "captured",
            "cognitive_status": "unreviewed",
            "metadata": {
                "title": "Seeded manual capture",
                "seed": True,
                "summary": "Ideas clipped from manual /api/capture.",
            },
            "capture_fingerprint": "seed-text-sha256",
            "fingerprint_algo": "sha256:text+channel",
            "capture_metadata": {
                "submitted_by": "seed_script",
                "note": "Manual text payload",
            },
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    ]


def seed_entries() -> int:
    settings = load_settings()
    engine = create_engine(settings.database_url, future=True)
    metadata_obj = MetaData()
    entries_table = Table("entries", metadata_obj, autoload_with=engine)

    records = build_seed_entries(datetime.now(timezone.utc))
    stmt = pg_insert(entries_table).values(records)
    update_cols = {
        col: stmt.excluded[col]
        for col in [
            "source_type",
            "source_channel",
            "source_path",
            "pipeline_status",
            "cognitive_status",
            "metadata",
            "capture_fingerprint",
            "fingerprint_algo",
            "capture_metadata",
            "updated_at",
        ]
    }

    with engine.begin() as conn:
        conn.execute(
            stmt.on_conflict_do_update(
                index_elements=[entries_table.c.entry_id], set_=update_cols
            )
        )

    return len(records)


def main() -> None:
    inserted = seed_entries()
    print(f"Seeded {inserted} entries into EF-06.")


if __name__ == "__main__":
    main()
