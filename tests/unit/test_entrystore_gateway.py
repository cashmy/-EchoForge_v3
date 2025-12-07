"""Tests for EF-06 EntryStore gateway helpers."""

from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway


def test_create_entry_sets_defaults_and_stores_metadata():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc", "fingerprint_algo": "sha256"},
    )

    assert record.entry_id
    assert record.pipeline_status == "ingested"
    assert record.cognitive_status == "unreviewed"
    assert record.metadata["capture_fingerprint"] == "abc"
    assert record.created_at.tzinfo is not None


def test_find_by_fingerprint_returns_snapshot():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc", "fingerprint_algo": "sha256"},
        pipeline_status="processing",
    )

    snapshot = gateway.find_by_fingerprint("abc", "watch_folder_audio")

    assert snapshot is not None
    assert snapshot.entry_id == record.entry_id
    assert snapshot.pipeline_status == "processing"


def test_update_pipeline_status_refreshes_entry():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc"},
        pipeline_status="captured",
    )

    updated = gateway.update_pipeline_status(
        record.entry_id, pipeline_status="queued_for_transcription"
    )

    assert updated.pipeline_status == "queued_for_transcription"
    assert updated.entry_id == record.entry_id
    assert updated.updated_at > record.updated_at
