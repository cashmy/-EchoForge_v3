"""Unit tests for EF-04 normalization worker."""

from __future__ import annotations

# from pathlib import Path
# from typing import Any, Dict, List, Optional

import pytest

from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.jobs import normalization_worker as worker
from tests.helpers.logging import (
    RecordingLogger,
    assert_extra_contains,
    assert_extra_has_keys,
    find_log,
)

pytestmark = [pytest.mark.ef04, pytest.mark.ef06, pytest.mark.inf02]


class RecordingJobQueue:
    def __init__(self) -> None:
        self.enqueued_jobs: list[tuple[str, dict]] = []

    def enqueue(self, job_type: str, payload: dict) -> None:
        self.enqueued_jobs.append((job_type, payload))


@pytest.fixture(autouse=True)
def reset_normalization_config(monkeypatch: pytest.MonkeyPatch) -> None:
    base_profile = {
        "max_input_chars": 100_000,
        "max_output_chars": 80_000,
        "remove_timestamps": True,
        "emit_segments": True,
        "segment_threshold_chars": 50,
        "preserve_markdown": False,
        "sentence_case_all_caps": False,
    }
    monkeypatch.setattr(worker, "_BASE_PROFILE", base_profile.copy())
    monkeypatch.setattr(worker, "_PROFILES", {})
    monkeypatch.setattr(worker, "_DEFAULT_PROFILE", "standard")
    monkeypatch.setattr(worker, "_WORKER_ID", "ef04::test")


@pytest.fixture()
def gateway() -> InMemoryEntryStoreGateway:
    return InMemoryEntryStoreGateway()


def _advance_pipeline_statuses(
    gateway: InMemoryEntryStoreGateway,
    entry_id: str,
    statuses: tuple[str, ...],
) -> None:
    for status in statuses:
        gateway.update_pipeline_status(entry_id, pipeline_status=status)


def _create_transcribed_entry(gateway: InMemoryEntryStoreGateway, text: str) -> str:
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_audio",
        source_path="/tmp/audio.wav",
        metadata={"capture_fingerprint": "fp-a", "fingerprint_algo": "sha256"},
        pipeline_status=PIPELINE_STATUS.INGESTED,
    )
    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.QUEUED_FOR_TRANSCRIPTION,
            PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
        ),
    )
    gateway.record_transcription_result(
        record.entry_id,
        text=text,
        segments=[{"text": text, "start_ms": 0, "end_ms": 1000}],
        metadata={"language": "en"},
        verbatim_path="/tmp/transcript.txt",
        verbatim_preview=text[:50],
        content_lang="en",
    )
    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
            PIPELINE_STATUS.QUEUED_FOR_NORMALIZATION,
        ),
    )
    return record.entry_id


def _create_extracted_entry(gateway: InMemoryEntryStoreGateway, text: str) -> str:
    record = gateway.create_entry(
        source_type="document",
        source_channel="watch_documents",
        source_path="/tmp/doc.txt",
        metadata={"capture_fingerprint": "fp-b", "fingerprint_algo": "sha256"},
        pipeline_status=PIPELINE_STATUS.INGESTED,
    )
    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.QUEUED_FOR_EXTRACTION,
            PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
        ),
    )
    gateway.record_extraction_result(
        record.entry_id,
        text=text,
        segments=[{"index": 0, "text": text, "char_count": len(text)}],
        metadata={"language": "en"},
        verbatim_path="/tmp/extracted.txt",
        verbatim_preview=text[:50],
        content_lang="en",
    )
    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.EXTRACTION_COMPLETE,
            PIPELINE_STATUS.QUEUED_FOR_NORMALIZATION,
        ),
    )
    return record.entry_id


def _create_normalization_ready_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    source_type: str,
    fingerprint: str,
) -> str:
    source_channel = "watch_audio" if source_type == "audio" else "watch_documents"
    record = gateway.create_entry(
        source_type=source_type,
        source_channel=source_channel,
        source_path="/tmp/input.bin",
        metadata={"capture_fingerprint": fingerprint, "fingerprint_algo": "sha256"},
        pipeline_status=PIPELINE_STATUS.INGESTED,
    )
    if source_type == "audio":
        advance = (
            PIPELINE_STATUS.QUEUED_FOR_TRANSCRIPTION,
            PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
            PIPELINE_STATUS.QUEUED_FOR_NORMALIZATION,
        )
    else:
        advance = (
            PIPELINE_STATUS.QUEUED_FOR_EXTRACTION,
            PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
            PIPELINE_STATUS.QUEUED_FOR_NORMALIZATION,
        )
    _advance_pipeline_statuses(gateway, record.entry_id, advance)
    return record.entry_id


def test_handle_normalizes_transcription_text_and_enqueues_semantics(
    gateway: InMemoryEntryStoreGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_id = _create_transcribed_entry(
        gateway,
        text="[00:01] Hello   world!\n\nSpeaker 1: This is a test.",
    )
    queue = RecordingJobQueue()
    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    worker.handle(
        {
            "entry_id": entry_id,
            "source": "transcription",
            "content_lang": "en",
            "correlation_id": "corr-norm-1",
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert record.normalized_text.startswith("Hello world!")
    assert record.pipeline_status == PIPELINE_STATUS.NORMALIZATION_COMPLETE
    assert record.normalization_metadata["raw_source"] == "transcription_text"
    assert record.normalization_metadata["segment_count"] >= 1
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_semantic"
    assert (capture_meta.get("normalization") or {}).get("profile") == "standard"
    assert queue.enqueued_jobs == [
        (
            "echo.semantic_enrich",
            {
                "entry_id": entry_id,
                "source": "normalization",
                "content_lang": "en",
                "chunk_count": record.normalization_metadata.get("chunk_count"),
                "correlation_id": "corr-norm-1",
            },
        )
    ]

    started = find_log(log.records, message="normalization_started", level="info")
    assert_extra_contains(
        started,
        entry_id=entry_id,
        stage="normalization",
        pipeline_status=PIPELINE_STATUS.NORMALIZATION_IN_PROGRESS,
        correlation_id="corr-norm-1",
        source="transcription",
    )
    assert_extra_has_keys(started, ["profile"])

    completed = find_log(log.records, message="normalization_completed", level="info")
    assert_extra_contains(
        completed,
        entry_id=entry_id,
        stage="normalization",
        pipeline_status=PIPELINE_STATUS.NORMALIZATION_COMPLETE,
        correlation_id="corr-norm-1",
    )
    assert completed["extra"].get("segment_count") == record.normalization_metadata.get(
        "segment_count"
    )
    assert completed["extra"].get("normalized_char_count") == len(
        record.normalized_text
    )


def test_handle_applies_overrides_and_segment_threshold(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    long_text = "Paragraph one." + "\n\n" + "Paragraph two." + "\n\n" + "- Bullet"
    entry_id = _create_extracted_entry(gateway, long_text)
    queue = RecordingJobQueue()

    worker.handle(
        {
            "entry_id": entry_id,
            "source": "document_extraction",
            "chunk_count": 99,
            "overrides": {"segment_threshold_chars": 10},
            "correlation_id": "corr-norm-2",
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert record.normalized_text.startswith("Paragraph one.")
    assert len(record.normalized_segments or []) >= 2
    assert record.normalization_metadata["chunk_count"] == 99
    assert queue.enqueued_jobs[0][1]["chunk_count"] == 99


def test_handle_records_failure_when_raw_text_missing(
    gateway: InMemoryEntryStoreGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_id = _create_normalization_ready_entry(
        gateway,
        source_type="audio",
        fingerprint="fp-c",
    )

    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    with pytest.raises(worker.NormalizationError):
        worker.handle(
            {
                "entry_id": entry_id,
                "source": "transcription",
                "correlation_id": "corr-norm-3",
            },
            entry_gateway=gateway,
            jobqueue_adapter=RecordingJobQueue(),
        )

    snapshot = gateway.get_entry(entry_id)
    assert snapshot.pipeline_status == PIPELINE_STATUS.NORMALIZATION_FAILED
    assert snapshot.normalization_error == {
        "code": "raw_text_missing",
        "message": "raw text is missing",
        "retryable": False,
    }
    failure = find_log(log.records, message="normalization_failed", level="error")
    assert_extra_contains(
        failure,
        entry_id=entry_id,
        stage="normalization",
        pipeline_status=PIPELINE_STATUS.NORMALIZATION_FAILED,
        error_code="raw_text_missing",
        retryable=False,
        correlation_id="corr-norm-3",
        source="transcription",
    )
