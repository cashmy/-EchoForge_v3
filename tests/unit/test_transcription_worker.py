"""Unit tests for EF-02 transcription worker."""

# Coverage: EF-02, EF-06, INF-02, INF-04

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.app.domain.ef01_capture.watch_folders import WATCH_SUBDIRECTORIES
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.jobs import transcription_worker as worker
from backend.app.jobs.transcription_worker import (
    LlmGatewayTranscriptionClient,
    TranscriptionError,
    TranscriptionOutput,
)
from tests.helpers.logging import (
    RecordingLogger,
    assert_extra_contains,
    assert_extra_has_keys,
    find_log,
)

pytestmark = [
    pytest.mark.ef02,
    pytest.mark.ef06,
    pytest.mark.inf02,
    pytest.mark.inf04,
]


@pytest.fixture(autouse=True)
def transcript_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "transcripts"
    monkeypatch.setattr(worker, "_TRANSCRIPT_OUTPUT_ROOT", str(root))
    monkeypatch.setattr(worker, "_TRANSCRIPT_PUBLIC_BASE_URL", None)
    return root


class RecordingJobQueue:
    """Simple stub that records enqueue calls for assertions."""

    def __init__(self) -> None:
        self.enqueued_jobs: list[tuple[str, dict]] = []

    def enqueue(self, job_type: str, payload: dict) -> None:
        self.enqueued_jobs.append((job_type, payload))


@dataclass
class SuccessfulTranscriptionClient:
    """Stub transcription client that returns a fixed transcript."""

    transcript_text: str = "transcribed text"

    def transcribe(
        self,
        *,
        source_path: str,
        media_type: str | None,
        language_hint: str | None,
        profile: str,
    ) -> TranscriptionOutput:
        return TranscriptionOutput(
            text=self.transcript_text,
            segments=[
                {
                    "text": self.transcript_text,
                    "start_ms": 0,
                    "end_ms": 1000,
                }
            ],
            metadata={
                "language": language_hint or "en",
                "media_type": media_type,
                "profile": profile,
                "source_path": source_path,
            },
        )


class FailingTranscriptionClient:
    """Stub client that always raises a retryable error."""

    def transcribe(
        self,
        *,
        source_path: str,
        media_type: str | None,
        language_hint: str | None,
        profile: str,
    ) -> TranscriptionOutput:
        raise TranscriptionError(
            "llm timeout",
            retryable=True,
            code="llm_timeout",
        )


class ExplodingTranscriptionClient:
    """Stub client that raises a generic exception to exercise fallback path."""

    def transcribe(
        self,
        *,
        source_path: str,
        media_type: str | None,
        language_hint: str | None,
        profile: str,
    ) -> TranscriptionOutput:
        raise RuntimeError("decoder blew up")


@pytest.fixture()
def gateway() -> InMemoryEntryStoreGateway:
    return InMemoryEntryStoreGateway()


def _create_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    source_path: str,
) -> str:
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_folder_audio",
        source_path=source_path,
        metadata={
            "capture_fingerprint": "fp-123",
            "fingerprint_algo": "sha256",
        },
        pipeline_status=PIPELINE_STATUS.QUEUED_FOR_TRANSCRIPTION,
    )
    return record.entry_id


def _create_processing_file(tmp_path) -> tuple[str, str]:
    root = tmp_path / "watch"
    for subdir in WATCH_SUBDIRECTORIES:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    processing_file = root / WATCH_SUBDIRECTORIES[1] / "audio.wav"
    processing_file.write_text("audio-bytes")
    return str(root), str(processing_file)


def test_llm_gateway_client_formats_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LlmGatewayTranscriptionClient()

    def fake_transcribe_audio(
        path: str,
        *,
        language_hint: str | None = None,
        profile: str = "transcribe_v1",
    ) -> dict:
        assert path == "/tmp/audio.wav"
        assert language_hint == "en"
        assert profile == "profile_a"
        return {
            "text": " hi there ",
            "segments": [
                {
                    "text": " hi there ",
                    "start": 1.0,
                    "end": 2.5,
                    "tokens": [1, 2, 3],
                }
            ],
            "language": "es",
            "confidence": 0.87,
            "model": "medium.en",
            "duration_ms": 2500,
        }

    monkeypatch.setattr(worker, "transcribe_audio", fake_transcribe_audio)

    result = client.transcribe(
        source_path="/tmp/audio.wav",
        media_type="audio/wav",
        language_hint="en",
        profile="profile_a",
    )

    assert result.text == " hi there "
    assert result.segments == [
        {"text": "hi there", "start_ms": 1000, "end_ms": 2500, "tokens": [1, 2, 3]}
    ]
    assert result.metadata == {
        "language": "es",
        "confidence": 0.87,
        "model": "medium.en",
        "duration_ms": 2500,
        "media_type": "audio/wav",
    }


def test_handle_records_transcription_and_enqueues_followup(
    gateway: InMemoryEntryStoreGateway,
    tmp_path,
    transcript_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, processing_path = _create_processing_file(tmp_path)
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    client = SuccessfulTranscriptionClient(transcript_text="hello world")

    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    worker.handle(
        {
            "entry_id": entry_id,
            "source_path": processing_path,
            "source_channel": "watch_folder_audio",
            "fingerprint": "fp-123",
            "media_type": "audio/wav",
            "language_hint": "en",
            "llm_profile": "test_profile",
            "correlation_id": "corr-001",
        },
        entry_gateway=gateway,
        transcription_client=client,
        jobqueue_adapter=queue,
    )

    record = gateway.get_entry(entry_id)
    assert record.transcription_text == "hello world"
    assert record.pipeline_status == PIPELINE_STATUS.TRANSCRIPTION_COMPLETE
    assert record.transcription_metadata["media_type"] == "audio/wav"
    assert record.transcription_metadata["processing_ms"] >= 0
    transcript_path = transcript_root / f"{entry_id}.txt"
    assert record.transcription_metadata["transcript_file_path"] == str(transcript_path)
    assert transcript_path.exists()
    assert transcript_path.read_text(encoding="utf-8") == "hello world"
    assert record.verbatim_path == str(transcript_path)
    assert record.verbatim_preview == "hello world"
    segments_path = transcript_root / f"{entry_id}.segments.json"
    assert segments_path.exists()
    events = record.metadata.get("capture_events")
    assert events is not None
    stage_events = [
        event["type"] for event in events if event["type"] != "pipeline_status_changed"
    ]
    assert stage_events == [
        "transcription_started",
        "transcription_completed",
        "transcription_file_rolled",
    ]
    processed_path = (
        Path(processing_path).parent.parent
        / WATCH_SUBDIRECTORIES[2]
        / Path(processing_path).name
    )
    assert not Path(processing_path).exists()
    assert processed_path.exists()
    assert queue.enqueued_jobs == [
        (
            "echo.normalize_entry",
            {
                "entry_id": entry_id,
                "source": "transcription",
                "correlation_id": "corr-001",
            },
        )
    ]
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processing_normalization"
    transcription_meta = capture_meta.get("transcription") or {}
    assert transcription_meta.get("source_path") == processing_path
    assert transcription_meta.get("source_channel") == "watch_folder_audio"
    assert transcription_meta.get("fingerprint") == "fp-123"

    started = find_log(log.records, message="transcription_started", level="info")
    assert_extra_contains(
        started,
        entry_id=entry_id,
        source_channel="watch_folder_audio",
        fingerprint="fp-123",
        correlation_id="corr-001",
        stage="transcription",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
    )
    assert_extra_has_keys(started, ["source_path"])

    completed = find_log(log.records, message="transcription_completed", level="info")
    assert_extra_contains(
        completed,
        entry_id=entry_id,
        source_channel="watch_folder_audio",
        correlation_id="corr-001",
        stage="transcription",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
    )
    assert completed["extra"].get("processing_ms") is not None
    assert completed["extra"].get("segment_count") == 1


def test_handle_records_failure_and_reraises(
    gateway: InMemoryEntryStoreGateway,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, processing_path = _create_processing_file(tmp_path)
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    client = FailingTranscriptionClient()

    payload = {
        "entry_id": entry_id,
        "source_path": processing_path,
        "source_channel": "watch_folder_audio",
        "fingerprint": "fp-123",
        "media_type": "audio/wav",
        "language_hint": "en",
        "llm_profile": "test_profile",
        "correlation_id": "corr-002",
    }

    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    with pytest.raises(TranscriptionError):
        worker.handle(
            payload,
            entry_gateway=gateway,
            transcription_client=client,
            jobqueue_adapter=queue,
        )

    record = gateway.get_entry(entry_id)
    assert record.pipeline_status == PIPELINE_STATUS.TRANSCRIPTION_FAILED
    assert record.transcription_error == {
        "code": "llm_timeout",
        "message": "llm timeout",
        "retryable": True,
    }
    assert record.verbatim_path is None
    events = record.metadata.get("capture_events")
    assert events is not None
    stage_events = [
        event["type"] for event in events if event["type"] != "pipeline_status_changed"
    ]
    assert stage_events[-2:] == [
        "transcription_failed",
        "transcription_file_rolled",
    ]
    failed_path = (
        Path(processing_path).parent.parent
        / WATCH_SUBDIRECTORIES[3]
        / Path(processing_path).name
    )
    assert failed_path.exists()
    assert not Path(processing_path).exists()
    assert queue.enqueued_jobs == []
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "failed"
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("stage") == "transcription"
    assert last_error.get("code") == "llm_timeout"

    failure = find_log(log.records, message="transcription_failed", level="exception")
    assert_extra_contains(
        failure,
        entry_id=entry_id,
        error_code="llm_timeout",
        retryable=True,
        correlation_id="corr-002",
        stage="transcription",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_FAILED,
    )


def test_handle_records_failure_on_unexpected_exception(
    gateway: InMemoryEntryStoreGateway,
    tmp_path,
) -> None:
    _, processing_path = _create_processing_file(tmp_path)
    entry_id = _create_entry(gateway, source_path=processing_path)
    queue = RecordingJobQueue()
    client = ExplodingTranscriptionClient()

    payload = {
        "entry_id": entry_id,
        "source_path": processing_path,
        "source_channel": "watch_folder_audio",
        "fingerprint": "fp-123",
        "media_type": "audio/wav",
        "language_hint": None,
        "llm_profile": "transcribe_v1",
        "correlation_id": "corr-003",
    }

    with pytest.raises(RuntimeError):
        worker.handle(
            payload,
            entry_gateway=gateway,
            transcription_client=client,
            jobqueue_adapter=queue,
        )

    record = gateway.get_entry(entry_id)
    assert record.pipeline_status == PIPELINE_STATUS.TRANSCRIPTION_FAILED
    assert record.transcription_error == {
        "code": "internal_error",
        "message": "decoder blew up",
        "retryable": False,
    }
    assert record.verbatim_path is None
    events = record.metadata.get("capture_events")
    assert events is not None
    stage_events = [
        event["type"] for event in events if event["type"] != "pipeline_status_changed"
    ]
    assert stage_events[-2] == "transcription_failed"
    assert stage_events[-1] == "transcription_file_rolled"
    capture_meta = record.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "failed"
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("stage") == "transcription"
    assert last_error.get("code") == "internal_error"
