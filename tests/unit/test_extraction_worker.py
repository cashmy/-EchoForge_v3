"""Unit tests for EF-03 extraction worker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.domain.ef01_capture.watch_folders import WATCH_SUBDIRECTORIES
from backend.app.domain.ef03_extraction import DocumentExtractionError
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.jobs import extraction_worker as worker
from tests.helpers.logging import (
    RecordingLogger,
    assert_extra_contains,
    assert_extra_has_keys,
    find_log,
)

pytestmark = [pytest.mark.ef03, pytest.mark.ef06, pytest.mark.inf02]


class RecordingJobQueue:
    def __init__(self) -> None:
        self.enqueued_jobs: list[tuple[str, dict]] = []

    def enqueue(self, job_type: str, payload: dict) -> None:
        self.enqueued_jobs.append((job_type, payload))


@pytest.fixture()
def gateway() -> InMemoryEntryStoreGateway:
    return InMemoryEntryStoreGateway()


@pytest.fixture(autouse=True)
def _reset_document_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure worker uses local watch root folders during tests."""

    monkeypatch.setattr(worker, "_PROCESSED_ROOT", None)
    monkeypatch.setattr(worker, "_FAILED_ROOT", None)
    verbatim_root = tmp_path / "verbatim"
    monkeypatch.setattr(worker, "_EXTRACTION_OUTPUT_ROOT", str(verbatim_root))
    monkeypatch.setattr(worker, "_EXTRACTION_PUBLIC_BASE_URL", None)
    segment_root = tmp_path / "segments"
    monkeypatch.setattr(worker, "_SEGMENT_CACHE_ROOT", str(segment_root))
    monkeypatch.setattr(worker, "_SEGMENT_CACHE_THRESHOLD", 1_000_000)


def _create_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    source_path: str,
    source_channel: str = "watch_documents",
) -> str:
    record = gateway.create_entry(
        source_type="document",
        source_channel=source_channel,
        source_path=source_path,
        metadata={
            "capture_fingerprint": "fp-001",
            "fingerprint_algo": "sha256",
        },
        pipeline_status=PIPELINE_STATUS.QUEUED_FOR_EXTRACTION,
    )
    return record.entry_id


def _create_processing_file(
    tmp_path: Path,
    filename: str = "note.txt",
    *,
    content: str = "Hello world",
) -> str:
    root = tmp_path / "documents"
    for subdir in WATCH_SUBDIRECTORIES:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    processing_path = root / WATCH_SUBDIRECTORIES[1] / filename
    processing_path.write_text(content, encoding="utf-8")
    return str(processing_path)


def test_handle_extracts_plain_text_and_enqueues_followup(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processing_path = _create_processing_file(tmp_path)
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    worker.handle(
        {
            "entry_id": entry_id,
            "source_path": processing_path,
            "source_channel": "watch_documents",
            "fingerprint": "fp-001",
            "source_mime": "text/plain",
            "language_hint": "en",
            "correlation_id": "corr-doc-1",
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert record.extracted_text.startswith("Hello world")
    assert record.pipeline_status == PIPELINE_STATUS.EXTRACTION_COMPLETE
    assert record.extraction_metadata["converter"] == "plain_text"
    verbatim_file = Path(worker._EXTRACTION_OUTPUT_ROOT) / f"{entry_id}.txt"
    assert verbatim_file.exists()
    assert record.verbatim_path == str(verbatim_file)
    assert record.extraction_metadata["extracted_text_file_path"] == str(verbatim_file)
    assert record.verbatim_preview == "Hello world"
    segment_count = record.extraction_metadata["segment_count"]
    processed_path = (
        Path(processing_path).parent.parent
        / WATCH_SUBDIRECTORIES[2]
        / Path(processing_path).name
    )
    assert processed_path.exists()
    assert not Path(processing_path).exists()
    capture_meta = record.metadata.get("capture_metadata") or {}
    document_meta = capture_meta.get("document") or {}
    assert capture_meta.get("ingest_state") == "processing_normalization"
    assert document_meta.get("source_mime") == "text/plain"
    assert document_meta.get("processed_path") == str(processed_path)
    assert document_meta.get("verbatim_path") == record.verbatim_path
    assert queue.enqueued_jobs == [
        (
            "echo.normalize_entry",
            {
                "entry_id": entry_id,
                "source": "document_extraction",
                "chunk_count": segment_count,
                "content_lang": "en",
                "correlation_id": "corr-doc-1",
            },
        )
    ]

    started = find_log(log.records, message="extraction_started", level="info")
    assert_extra_contains(
        started,
        entry_id=entry_id,
        source_channel="watch_documents",
        stage="extraction",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
        correlation_id="corr-doc-1",
    )
    assert_extra_has_keys(started, ["source_path", "source_mime", "fingerprint"])

    completed = find_log(log.records, message="extraction_completed", level="info")
    assert_extra_contains(
        completed,
        entry_id=entry_id,
        source_channel="watch_documents",
        stage="extraction",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_COMPLETE,
        correlation_id="corr-doc-1",
    )
    assert completed["extra"].get("processing_ms") is not None
    assert completed["extra"].get("segment_count") == segment_count


def test_handle_caches_large_segments_when_threshold_exceeded(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processing_path = _create_processing_file(tmp_path)
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    monkeypatch.setattr(worker, "_SEGMENT_CACHE_THRESHOLD", 10)

    worker.handle(
        {
            "entry_id": entry_id,
            "source_path": processing_path,
            "source_channel": "watch_documents",
            "fingerprint": "fp-001",
            "source_mime": "text/plain",
            "language_hint": None,
            "correlation_id": "corr-doc-cache",
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert record.extraction_segments is None
    cache_path = Path(worker._SEGMENT_CACHE_ROOT) / f"{entry_id}.segments.json"
    assert cache_path.exists()
    cached_segments = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached_segments[0]["text"].startswith("Hello world")
    assert record.extraction_metadata["segment_cache_path"] == str(cache_path)
    assert record.extraction_metadata["segment_cache_bytes"] > 10
    assert (
        queue.enqueued_jobs[0][1]["chunk_count"]
        == record.extraction_metadata["segment_count"]
    )


def test_handle_truncates_large_text_when_over_limit(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_text = "Lorem ipsum " * 2000
    processing_path = _create_processing_file(
        tmp_path,
        filename="long.txt",
        content=long_text,
    )
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    monkeypatch.setattr(worker, "_MAX_INLINE_CHARS", 100)

    worker.handle(
        {
            "entry_id": entry_id,
            "source_path": processing_path,
            "source_channel": "watch_documents",
            "fingerprint": "fp-001",
            "source_mime": "text/plain",
            "language_hint": None,
            "correlation_id": "corr-doc-long",
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert len(record.extracted_text or "") == 100
    assert record.extraction_metadata["truncated"] is True
    assert record.extraction_metadata["inline_char_limit"] == 100
    assert record.extraction_metadata["extracted_char_count"] == len(long_text)
    verbatim_file = Path(record.extraction_metadata["extracted_text_file_path"])
    assert verbatim_file.read_text(encoding="utf-8") == long_text


def test_handle_respects_metadata_override_for_inline_limit(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
) -> None:
    long_text = "Alpha beta gamma " * 1000
    processing_path = _create_processing_file(
        tmp_path,
        filename="long_override.txt",
        content=long_text,
    )
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()

    worker.handle(
        {
            "entry_id": entry_id,
            "source_path": processing_path,
            "source_channel": "watch_documents",
            "fingerprint": "fp-override",
            "source_mime": "text/plain",
            "language_hint": None,
            "correlation_id": "corr-doc-override",
            "metadata_overrides": {"max_inline_chars": 80},
        },
        entry_gateway=gateway,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert len(record.extracted_text or "") == 80
    assert record.extraction_metadata["inline_char_limit"] == 80
    assert record.extraction_metadata["truncated"] is True
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_normalization"


def test_handle_records_failure_on_document_error(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processing_path = _create_processing_file(tmp_path, filename="note.bin")
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()

    def _raise_doc_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise DocumentExtractionError(
            "ocr required",
            code="ocr_required",
            retryable=True,
        )

    monkeypatch.setattr(worker, "extract_document", _raise_doc_error)
    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    with pytest.raises(DocumentExtractionError):
        worker.handle(
            {
                "entry_id": entry_id,
                "source_path": processing_path,
                "source_channel": "watch_documents",
                "fingerprint": "fp-001",
                "source_mime": "application/pdf",
                "language_hint": None,
                "correlation_id": "corr-doc-2",
            },
            entry_gateway=gateway,
            jobqueue_adapter=queue,
        )

    record = gateway.get_entry(entry_id)
    assert record.pipeline_status == PIPELINE_STATUS.EXTRACTION_FAILED
    assert record.extraction_error == {
        "code": "ocr_required",
        "message": "ocr required",
        "retryable": True,
    }
    capture_meta = record.metadata.get("capture_metadata") or {}
    failure_doc = capture_meta.get("document") or {}
    assert capture_meta.get("ingest_state") == "failed"
    assert capture_meta.get("last_error", {}).get("code") == "ocr_required"
    failed_path = (
        Path(processing_path).parent.parent
        / WATCH_SUBDIRECTORIES[3]
        / Path(processing_path).name
    )
    assert failed_path.exists()
    assert failure_doc.get("failed_path") == str(failed_path)
    assert queue.enqueued_jobs == []

    failure = find_log(log.records, message="extraction_failed", level="exception")
    assert_extra_contains(
        failure,
        entry_id=entry_id,
        error_code="ocr_required",
        retryable=True,
        correlation_id="corr-doc-2",
        stage="extraction",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_FAILED,
    )


def test_handle_records_failure_on_unexpected_exception(
    gateway: InMemoryEntryStoreGateway,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processing_path = _create_processing_file(tmp_path, filename="note2.txt")
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()

    def _explode(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "extract_document", _explode)

    with pytest.raises(RuntimeError):
        worker.handle(
            {
                "entry_id": entry_id,
                "source_path": processing_path,
                "source_channel": "watch_documents",
                "fingerprint": "fp-001",
                "source_mime": "text/plain",
                "language_hint": None,
                "correlation_id": "corr-doc-3",
            },
            entry_gateway=gateway,
            jobqueue_adapter=queue,
        )

    record = gateway.get_entry(entry_id)
    assert record.pipeline_status == PIPELINE_STATUS.EXTRACTION_FAILED
    assert record.extraction_error == {
        "code": "internal_error",
        "message": "boom",
        "retryable": False,
    }
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "failed"
    assert capture_meta.get("last_error", {}).get("code") == "internal_error"
    failed_path = (
        Path(processing_path).parent.parent
        / WATCH_SUBDIRECTORIES[3]
        / Path(processing_path).name
    )
    assert failed_path.exists()
    assert (capture_meta.get("document") or {}).get("failed_path") == str(failed_path)
    assert queue.enqueued_jobs == []
