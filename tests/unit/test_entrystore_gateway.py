"""Tests for EF-06 EntryStore gateway helpers."""

# Coverage: EF-06

import sqlalchemy as sa
import pytest

from backend.app.domain.ef06_entrystore.gateway import (
    InMemoryEntryStoreGateway,
    PostgresEntryStoreGateway,
)

pytestmark = [pytest.mark.ef06]


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
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "captured"
    assert capture_meta.get("pipeline_status") == "ingested"
    history = capture_meta.get("pipeline_history") or []
    assert history[0]["pipeline_status"] == "ingested"


def test_find_by_fingerprint_returns_snapshot():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc", "fingerprint_algo": "sha256"},
        pipeline_status="queued_for_transcription",
    )

    snapshot = gateway.find_by_fingerprint("abc", "watch_folder_audio")

    assert snapshot is not None
    assert snapshot.entry_id == record.entry_id
    assert snapshot.pipeline_status == "queued_for_transcription"


def test_update_pipeline_status_tracks_ingest_state_and_events():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc"},
        pipeline_status="captured",
    )

    queued = gateway.update_pipeline_status(
        record.entry_id, pipeline_status="queued_for_transcription"
    )
    capture_meta = queued.metadata.get("capture_metadata") or {}
    assert queued.pipeline_status == "queued_for_transcription"
    assert capture_meta.get("ingest_state") == "queued_for_transcription"
    assert (
        queued.metadata.get("capture_events")[-1]["type"] == "pipeline_status_changed"
    )

    in_progress = gateway.update_pipeline_status(
        record.entry_id, pipeline_status="transcription_in_progress"
    )
    capture_meta = in_progress.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_transcription"
    history = capture_meta.get("pipeline_history") or []
    assert history[-1]["pipeline_status"] == "transcription_in_progress"
    assert (
        in_progress.metadata.get("capture_events")[-1]["data"]["to_ingest_state"]
        == "processing_transcription"
    )

    normalization_ready = gateway.update_pipeline_status(
        record.entry_id, pipeline_status="transcription_complete"
    )
    capture_meta = normalization_ready.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_normalization"
    assert (
        normalization_ready.metadata.get("capture_events")[-1]["data"][
            "pipeline_status"
        ]
        == "transcription_complete"
    )
    assert normalization_ready.entry_id == record.entry_id
    assert normalization_ready.updated_at >= in_progress.updated_at


def test_update_pipeline_status_rejects_invalid_jump():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/file.wav",
        metadata={"capture_fingerprint": "abc"},
        pipeline_status="captured",
    )

    with pytest.raises(ValueError):
        gateway.update_pipeline_status(
            record.entry_id, pipeline_status="semantic_in_progress"
        )


@pytest.fixture()
def postgres_gateway() -> PostgresEntryStoreGateway:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = sa.MetaData()
    entries = sa.Table(
        "entries",
        metadata,
        sa.Column("entry_id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_channel", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("pipeline_status", sa.String(length=64), nullable=False),
        sa.Column("cognitive_status", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capture_fingerprint", sa.Text(), nullable=True),
        sa.Column("fingerprint_algo", sa.String(length=64), nullable=True),
        sa.Column("capture_metadata", sa.JSON(), nullable=True),
        sa.Column("verbatim_path", sa.Text(), nullable=True),
        sa.Column("verbatim_preview", sa.Text(), nullable=True),
        sa.Column("content_lang", sa.String(length=12), nullable=True),
        sa.Column("transcription_text", sa.Text(), nullable=True),
        sa.Column("transcription_segments", sa.JSON(), nullable=True),
        sa.Column("transcription_metadata", sa.JSON(), nullable=False, default=dict),
        sa.Column("transcription_error", sa.JSON(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_segments", sa.JSON(), nullable=True),
        sa.Column("extraction_metadata", sa.JSON(), nullable=True),
        sa.Column("extraction_error", sa.JSON(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("normalized_segments", sa.JSON(), nullable=True),
        sa.Column("normalization_metadata", sa.JSON(), nullable=True),
        sa.Column("normalization_error", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("display_title", sa.Text(), nullable=True),
        sa.Column("summary_model", sa.String(length=128), nullable=True),
        sa.Column("semantic_tags", sa.JSON(), nullable=True),
        sa.Column("type_id", sa.String(length=128), nullable=True),
        sa.Column("type_label", sa.String(length=128), nullable=True),
        sa.Column("domain_id", sa.String(length=128), nullable=True),
        sa.Column("domain_label", sa.String(length=128), nullable=True),
        sa.Column("classification_model", sa.String(length=128), nullable=True),
        sa.Column("is_classified", sa.Boolean(), nullable=False, default=False),
    )
    metadata.create_all(engine)
    return PostgresEntryStoreGateway(engine=engine, table=entries)


def test_postgres_gateway_round_trip(postgres_gateway: PostgresEntryStoreGateway):
    record = postgres_gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/audio.wav",
        metadata={
            "capture_fingerprint": "pg-fp-1",
            "fingerprint_algo": "sha256",
        },
    )

    assert record.metadata["capture_fingerprint"] == "pg-fp-1"

    updated = postgres_gateway.update_pipeline_status(
        record.entry_id, pipeline_status="queued_for_transcription"
    )
    assert updated.pipeline_status == "queued_for_transcription"

    snapshot = postgres_gateway.find_by_fingerprint("pg-fp-1", "watch_folder_audio")
    assert snapshot is not None
    assert snapshot.entry_id == record.entry_id


def test_postgres_pipeline_transition_persists_capture_metadata(
    postgres_gateway: PostgresEntryStoreGateway,
):
    record = postgres_gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/audio.wav",
        metadata={
            "capture_fingerprint": "pg-transition",
            "fingerprint_algo": "sha256",
        },
    )

    updated = postgres_gateway.update_pipeline_status(
        record.entry_id, pipeline_status="queued_for_transcription"
    )
    capture_meta = updated.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "queued_for_transcription"
    events = updated.metadata.get("capture_events") or []
    assert events[-1]["type"] == "pipeline_status_changed"

    snapshot = postgres_gateway.get_entry(record.entry_id)
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "queued_for_transcription"
    assert (snapshot.metadata.get("capture_events") or [])[-1][
        "type"
    ] == "pipeline_status_changed"


def test_postgres_gateway_normalization_updates(
    postgres_gateway: PostgresEntryStoreGateway,
):
    record = postgres_gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/audio.wav",
        metadata={
            "capture_fingerprint": "pg-norm",
            "fingerprint_algo": "sha256",
        },
    )

    success = postgres_gateway.record_normalization_result(
        record.entry_id,
        text="hello world",
        segments=[{"index": 0, "text": "hello world", "char_count": 11}],
        metadata={"raw_source": "transcription_text", "worker_id": "norm"},
    )

    assert success.normalized_text == "hello world"
    assert success.normalized_segments[0]["text"] == "hello world"
    assert success.normalization_metadata["worker_id"] == "norm"

    failure = postgres_gateway.record_normalization_failure(
        record.entry_id,
        error_code="raw_text_missing",
        message="no text",
        retryable=False,
    )
    assert failure.normalization_error == {
        "code": "raw_text_missing",
        "message": "no text",
        "retryable": False,
    }


def test_postgres_gateway_transcription_updates(
    postgres_gateway: PostgresEntryStoreGateway,
):
    record = postgres_gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path="/tmp/audio.wav",
        metadata={
            "capture_fingerprint": "pg-fp-2",
            "fingerprint_algo": "sha256",
        },
        pipeline_status="queued_for_transcription",
    )

    result = postgres_gateway.record_transcription_result(
        record.entry_id,
        text="hello world",
        segments=[{"text": "hello world", "start_ms": 0, "end_ms": 1000}],
        metadata={"language": "en", "processing_ms": 100},
        verbatim_path="/transcripts/demo.txt",
        verbatim_preview="hello world",
        content_lang="en",
    )

    assert result.transcription_text == "hello world"
    assert result.verbatim_path == "/transcripts/demo.txt"
    assert result.transcription_metadata["language"] == "en"
    assert result.transcription_metadata["processing_ms"] == 100

    failure = postgres_gateway.record_transcription_failure(
        record.entry_id,
        error_code="internal_error",
        message="boom",
        retryable=False,
    )
    assert failure.transcription_error == {
        "code": "internal_error",
        "message": "boom",
        "retryable": False,
    }

    updated = postgres_gateway.record_capture_event(
        record.entry_id,
        event_type="transcription_started",
        data={"pipeline_status": "transcription_in_progress"},
    )
    events = updated.metadata.get("capture_events")
    assert events is not None
    assert events[-1]["type"] == "transcription_started"


def test_inmemory_merge_capture_metadata_updates_nested():
    gateway = InMemoryEntryStoreGateway()
    record = gateway.create_entry(
        source_type="document",
        source_channel="watch_documents",
        source_path="/tmp/doc.pdf",
        metadata={"capture_fingerprint": "merge-fp", "fingerprint_algo": "sha256"},
    )

    gateway.merge_capture_metadata(
        record.entry_id,
        patch={
            "ingest_state": "processing_extraction",
            "document": {"source_mime": "application/pdf"},
        },
    )

    updated = gateway.get_entry(record.entry_id)
    capture_meta = updated.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_extraction"
    assert (capture_meta.get("document") or {}).get("source_mime") == "application/pdf"


def test_postgres_merge_capture_metadata_persists_changes(
    postgres_gateway: PostgresEntryStoreGateway,
):
    record = postgres_gateway.create_entry(
        source_type="document",
        source_channel="watch_documents",
        source_path="/tmp/doc.pdf",
        metadata={
            "capture_fingerprint": "pg-merge",
            "fingerprint_algo": "sha256",
        },
    )

    postgres_gateway.merge_capture_metadata(
        record.entry_id,
        patch={
            "ingest_state": "processing_extraction",
            "document": {"source_mime": "application/pdf"},
        },
    )

    snapshot = postgres_gateway.find_by_fingerprint("pg-merge", "watch_documents")
    assert snapshot is not None
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_extraction"
    assert (capture_meta.get("document") or {}).get("source_mime") == "application/pdf"


def test_update_entry_taxonomy_inmemory_handles_partial_dimensions():
    gateway = InMemoryEntryStoreGateway()
    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/doc.txt",
        metadata={"capture_fingerprint": "tax-fp", "fingerprint_algo": "sha256"},
    )

    first = gateway.update_entry_taxonomy(
        entry.entry_id,
        type_id="project_note",
        type_label="Project Note",
        domain_id=None,
        domain_label=None,
    )

    assert first.type_id == "project_note"
    assert first.type_label == "Project Note"
    assert first.domain_label is None
    assert first.is_classified is False

    second = gateway.update_entry_taxonomy(
        entry.entry_id,
        type_id="project_note",
        type_label="Project Note",
        domain_id="product_ops",
        domain_label="Product Ops",
    )

    assert second.domain_id == "product_ops"
    assert second.domain_label == "Product Ops"
    assert second.is_classified is True


def test_update_entry_taxonomy_postgres_updates_columns(
    postgres_gateway: PostgresEntryStoreGateway,
):
    entry = postgres_gateway.create_entry(
        source_type="audio",
        source_channel="watch_audio",
        source_path="/tmp/audio.wav",
        metadata={"capture_fingerprint": "pg-tax", "fingerprint_algo": "sha256"},
    )

    updated = postgres_gateway.update_entry_taxonomy(
        entry.entry_id,
        type_id="incident",
        type_label="Incident",
        domain_id="sre",
        domain_label="SRE",
    )

    assert updated.type_id == "incident"
    assert updated.type_label == "Incident"
    assert updated.domain_id == "sre"
    assert updated.is_classified is True

    snapshot = postgres_gateway.get_entry(entry.entry_id)
    assert snapshot.domain_label == "SRE"
