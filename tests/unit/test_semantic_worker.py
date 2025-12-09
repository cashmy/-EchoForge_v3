"""Unit tests for the EF-05 semantic worker."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.infra.llm_gateway import PromptSpec, SemanticGatewayError
from backend.app.jobs import semantic_worker as worker
from tests.helpers.logging import (
    RecordingLogger,
    assert_extra_contains,
    assert_extra_has_keys,
    find_log,
)

pytestmark = [pytest.mark.ef05, pytest.mark.ef06, pytest.mark.inf04]


class RecordingSemanticClient:
    def __init__(self, response: Optional[Dict[str, Any]] = None) -> None:
        self.calls: list[Dict[str, Any]] = []
        self._response = response or {
            "summary": "Stub summary output.",
            "display_title": "Stub title",
            "model_used": "stub:model",
            "tags": ["EchoForge", "Semantics"],
            "type_label": "ArchitectureNote",
            "domain_label": "Engineering",
        }

    def generate_semantic_response(
        self,
        *,
        profile: str,
        prompt: PromptSpec,
        model_hint: str = "default",
        user_model_override: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "profile": profile,
                "model_hint": model_hint,
                "user_model_override": user_model_override,
                "correlation_id": correlation_id,
                "prompt": prompt,
            }
        )
        return SimpleNamespace(**self._response)


@pytest.fixture(autouse=True)
def reset_summary_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        worker,
        "_SUMMARY_CONFIG",
        {
            "max_preview_chars": 200,
            "max_deep_chars": 500,
            "max_retry_attempts": 3,
            "retry_backoff_ms": 0,
        },
    )


@pytest.fixture()
def gateway() -> InMemoryEntryStoreGateway:
    return InMemoryEntryStoreGateway()


def _advance_pipeline_statuses(
    gateway: InMemoryEntryStoreGateway,
    entry_id: str,
    statuses: Tuple[str, ...],
) -> None:
    for status in statuses:
        gateway.update_pipeline_status(entry_id, pipeline_status=status)


def _create_semantics_ready_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    normalized_text: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    entry_metadata = metadata or {
        "capture_fingerprint": "sem-helper-fp",
        "fingerprint_algo": "sha256",
    }
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_audio",
        source_path="/tmp/audio.wav",
        metadata=dict(entry_metadata),
        pipeline_status=PIPELINE_STATUS.INGESTED,
    )

    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.QUEUED_FOR_TRANSCRIPTION,
            PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
            PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
            PIPELINE_STATUS.QUEUED_FOR_NORMALIZATION,
            PIPELINE_STATUS.NORMALIZATION_IN_PROGRESS,
        ),
    )

    if normalized_text is not None:
        gateway.record_normalization_result(
            record.entry_id,
            text=normalized_text,
            segments=None,
            metadata={"chunk_count": 2},
        )

    _advance_pipeline_statuses(
        gateway,
        record.entry_id,
        (
            PIPELINE_STATUS.NORMALIZATION_COMPLETE,
            PIPELINE_STATUS.QUEUED_FOR_SEMANTICS,
        ),
    )

    return record.entry_id


def _create_normalized_entry(
    gateway: InMemoryEntryStoreGateway,
    *,
    normalized_text: Optional[str] = None,
) -> str:
    return _create_semantics_ready_entry(
        gateway,
        normalized_text=normalized_text or "Normalized text ready for EF-05 semantics.",
        metadata={"capture_fingerprint": "sem-fp-1", "fingerprint_algo": "sha256"},
    )


def test_handle_persists_summary_and_capture_metadata(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    entry_id = _create_normalized_entry(gateway)
    client = RecordingSemanticClient()

    worker.handle(
        {
            "entry_id": entry_id,
            "correlation_id": "corr-sem-1",
        },
        entry_gateway=gateway,
        llm_client=client,
    )

    snapshot = gateway.get_entry(entry_id)
    assert snapshot.summary == "Stub summary output."
    assert snapshot.display_title == "Stub title"
    assert snapshot.summary_model == "stub:model"
    assert snapshot.semantic_tags == ["echoforge", "semantics"]
    assert snapshot.type_label == "ArchitectureNote"
    assert snapshot.domain_label == "Engineering"
    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_COMPLETE

    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processed"
    semantics_meta = capture_meta.get("semantics") or {}
    assert semantics_meta.get("profile") == "echo_summary_v1"
    assert semantics_meta.get("mode") == "deep"
    assert semantics_meta.get("tags") == ["echoforge", "semantics"]
    assert semantics_meta.get("type_label") == "ArchitectureNote"
    assert semantics_meta.get("domain_label") == "Engineering"
    assert semantics_meta.get("attempts") == 1

    assert client.calls and client.calls[0]["profile"] == "echo_summary_v1"


def test_preview_mode_truncates_prompt_and_records_capture_metadata(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    long_text = "0123456789" * 200  # 2000 characters > max_preview_chars
    entry_id = _create_normalized_entry(gateway, normalized_text=long_text)
    client = RecordingSemanticClient()

    worker.handle(
        {
            "entry_id": entry_id,
            "mode": "preview",
            "correlation_id": "corr-preview-1",
        },
        entry_gateway=gateway,
        llm_client=client,
    )

    assert client.calls, "LLM client should be invoked"
    prompt_text = client.calls[0]["prompt"].user
    assert len(prompt_text) == 200
    assert prompt_text == long_text[:200]

    snapshot = gateway.get_entry(entry_id)
    capture_events = snapshot.metadata.get("capture_events") or []
    event_types = {event.get("type") for event in capture_events}
    assert {"semantic_started", "semantic_completed"}.issubset(event_types)

    started_event = next(
        event for event in capture_events if event.get("type") == "semantic_started"
    )
    completed_event = next(
        event for event in capture_events if event.get("type") == "semantic_completed"
    )
    assert started_event.get("data", {}).get("mode") == "preview"
    assert completed_event.get("data", {}).get("mode") == "preview"

    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    semantics_meta = capture_meta.get("semantics") or {}
    assert semantics_meta.get("mode") == "preview"
    assert semantics_meta.get("input_char_count") == 200


def test_handle_missing_normalized_text_records_failure(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    entry_id = _create_semantics_ready_entry(
        gateway,
        normalized_text=None,
        metadata={"capture_fingerprint": "sem-fp-2", "fingerprint_algo": "sha256"},
    )

    with pytest.raises(worker.SemanticWorkerError):
        worker.handle(
            {"entry_id": entry_id},
            entry_gateway=gateway,
            llm_client=RecordingSemanticClient(),
        )

    snapshot = gateway.get_entry(entry_id)
    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_FAILED
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "failed"
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("stage") == "semantics"


def test_classify_operation_preserves_summary_and_records_operation(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    entry_id = _create_normalized_entry(gateway)
    gateway.save_summary(
        entry_id,
        summary="Existing semantic summary.",
        display_title="Existing title",
        model_used="stub:previous",
        semantic_tags=["baseline"],
    )
    classify_response = {
        "summary": None,
        "display_title": None,
        "tags": ["ops-triage"],
        "model_used": "stub:classify",
        "type_label": "IncidentReport",
        "domain_label": "Operations",
    }
    client = RecordingSemanticClient(response=classify_response)

    worker.handle(
        {
            "entry_id": entry_id,
            "operation": "classify_v1",
            "classification_hint": "Focus on operations triage.",
            "correlation_id": "corr-classify-1",
        },
        entry_gateway=gateway,
        llm_client=client,
    )

    snapshot = gateway.get_entry(entry_id)
    assert snapshot.summary == "Existing semantic summary."
    assert snapshot.display_title == "Existing title"
    assert snapshot.semantic_tags == ["ops-triage"]
    assert snapshot.type_label == "IncidentReport"
    assert snapshot.domain_label == "Operations"

    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    semantics_meta = capture_meta.get("semantics") or {}
    assert semantics_meta.get("operation") == "classify_v1"
    assert semantics_meta.get("tags") == ["ops-triage"]
    assert semantics_meta.get("type_label") == "IncidentReport"
    assert semantics_meta.get("domain_label") == "Operations"

    capture_events = snapshot.metadata.get("capture_events") or []
    started_event = next(
        event for event in capture_events if event.get("type") == "semantic_started"
    )
    completed_event = next(
        event for event in capture_events if event.get("type") == "semantic_completed"
    )
    assert started_event.get("data", {}).get("operation") == "classify_v1"
    assert completed_event.get("data", {}).get("operation") == "classify_v1"

    assert client.calls, "LLM client should capture profile"
    call = client.calls[0]
    assert call["profile"] == "echo_classify_v1"
    assert call["prompt"].user_hint == "Focus on operations triage."


def test_handle_logs_start_and_completion_details(
    gateway: InMemoryEntryStoreGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry_id = _create_normalized_entry(gateway)
    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    worker.handle(
        {
            "entry_id": entry_id,
            "correlation_id": "corr-log-1",
        },
        entry_gateway=gateway,
        llm_client=RecordingSemanticClient(),
    )

    started = find_log(log.records, message="semantic_job_started", level="info")
    assert_extra_contains(
        started,
        entry_id=entry_id,
        mode="auto",
        operation="summarize_v1",
        profile="echo_summary_v1",
        correlation_id="corr-log-1",
        stage="semantics",
        pipeline_status=PIPELINE_STATUS.SEMANTIC_IN_PROGRESS,
    )
    assert_extra_has_keys(started, ["model_hint"])

    completed = find_log(log.records, message="semantic_job_completed", level="info")
    assert_extra_contains(
        completed,
        entry_id=entry_id,
        mode="deep",
        operation="summarize_v1",
        profile="echo_summary_v1",
        stage="semantics",
        pipeline_status=PIPELINE_STATUS.SEMANTIC_COMPLETE,
    )
    assert completed["extra"].get("processing_ms") is not None
    assert completed["extra"].get("attempts") == 1
    assert completed["extra"].get("tags") == ["echoforge", "semantics"]
    assert completed["extra"].get("summary_confidence") is None
    assert completed["extra"].get("classification_confidence") is None


def test_handle_logs_failure_details(
    gateway: InMemoryEntryStoreGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry_id = _create_semantics_ready_entry(
        gateway,
        normalized_text=None,
        metadata={"capture_fingerprint": "sem-fp-3", "fingerprint_algo": "sha256"},
    )
    log = RecordingLogger()
    monkeypatch.setattr(worker, "logger", log)

    with pytest.raises(worker.SemanticWorkerError):
        worker.handle(
            {
                "entry_id": entry_id,
                "correlation_id": "corr-log-2",
            },
            entry_gateway=gateway,
            llm_client=RecordingSemanticClient(),
        )

    failure = find_log(log.records, message="semantic_job_failed", level="error")
    assert_extra_contains(
        failure,
        entry_id=entry_id,
        operation="summarize_v1",
        error_code="semantic_missing_normalized_text",
        retryable=False,
        correlation_id="corr-log-2",
        stage="semantics",
        pipeline_status=PIPELINE_STATUS.SEMANTIC_FAILED,
    )


class FlakySemanticClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_semantic_response(
        self, **kwargs: Any
    ) -> Any:  # pragma: no cover - simple helper
        self.calls += 1
        if self.calls == 1:
            raise SemanticGatewayError("timeout", code="llm_timeout", retryable=True)
        client = RecordingSemanticClient()
        return client.generate_semantic_response(**kwargs)


class AlwaysFailingClient:
    def __init__(self, *, retryable: bool) -> None:
        self.retryable = retryable

    def generate_semantic_response(self, **_: Any) -> Any:  # pragma: no cover - helper
        raise SemanticGatewayError("boom", code="llm_timeout", retryable=self.retryable)


def test_handle_retries_retryable_errors(
    gateway: InMemoryEntryStoreGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry_id = _create_normalized_entry(gateway)
    monkeypatch.setattr(worker.time, "sleep", lambda _: None)

    worker.handle(
        {"entry_id": entry_id},
        entry_gateway=gateway,
        llm_client=FlakySemanticClient(),
    )

    snapshot = gateway.get_entry(entry_id)
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    semantics_meta = capture_meta.get("semantics") or {}
    assert semantics_meta.get("attempts") == 2


def test_handle_stops_after_max_attempts(
    gateway: InMemoryEntryStoreGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry_id = _create_normalized_entry(gateway)
    monkeypatch.setattr(worker.time, "sleep", lambda _: None)

    with pytest.raises(worker.SemanticWorkerError):
        worker.handle(
            {"entry_id": entry_id},
            entry_gateway=gateway,
            llm_client=AlwaysFailingClient(retryable=True),
        )

    snapshot = gateway.get_entry(entry_id)
    assert snapshot.pipeline_status == PIPELINE_STATUS.SEMANTIC_FAILED
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("retryable") is True
