"""Unit tests for the EF-05 semantic worker."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.infra.llm_gateway import PromptSpec, SemanticGatewayError
from backend.app.jobs import semantic_worker as worker

pytestmark = [pytest.mark.ef05, pytest.mark.ef06, pytest.mark.inf04]


class RecordingSemanticClient:
    def __init__(self) -> None:
        self.calls: list[Dict[str, Any]] = []

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
        return SimpleNamespace(
            summary="Stub summary output.",
            display_title="Stub title",
            model_used="stub:model",
            tags=["EchoForge", "Semantics"],
            type_label="ArchitectureNote",
            domain_label="Engineering",
        )


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


def _create_normalized_entry(gateway: InMemoryEntryStoreGateway) -> str:
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_audio",
        source_path="/tmp/audio.wav",
        metadata={"capture_fingerprint": "sem-fp-1", "fingerprint_algo": "sha256"},
        pipeline_status="queued_for_semantics",
    )
    gateway.record_normalization_result(
        record.entry_id,
        text="Normalized text ready for EF-05 semantics.",
        segments=None,
        metadata={"chunk_count": 2},
    )
    return record.entry_id


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
    assert snapshot.semantic_tags == ["EchoForge", "Semantics"]
    assert snapshot.type_label == "ArchitectureNote"
    assert snapshot.domain_label == "Engineering"
    assert snapshot.pipeline_status == "semantic_complete"

    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "processed"
    semantics_meta = capture_meta.get("semantics") or {}
    assert semantics_meta.get("profile") == "echo_summary_v1"
    assert semantics_meta.get("mode") == "deep"
    assert semantics_meta.get("tags") == ["EchoForge", "Semantics"]
    assert semantics_meta.get("type_label") == "ArchitectureNote"
    assert semantics_meta.get("domain_label") == "Engineering"
    assert semantics_meta.get("attempts") == 1

    assert client.calls and client.calls[0]["profile"] == "echo_summary_v1"


def test_handle_missing_normalized_text_records_failure(
    gateway: InMemoryEntryStoreGateway,
) -> None:
    record = gateway.create_entry(
        source_type="audio",
        source_channel="watch_audio",
        source_path="/tmp/audio.wav",
        metadata={"capture_fingerprint": "sem-fp-2", "fingerprint_algo": "sha256"},
        pipeline_status="queued_for_semantics",
    )

    with pytest.raises(worker.SemanticWorkerError):
        worker.handle(
            {"entry_id": record.entry_id},
            entry_gateway=gateway,
            llm_client=RecordingSemanticClient(),
        )

    snapshot = gateway.get_entry(record.entry_id)
    assert snapshot.pipeline_status == "semantic_failed"
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    assert capture_meta.get("ingest_state") == "failed"
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("stage") == "semantics"


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
    assert snapshot.pipeline_status == "semantic_failed"
    capture_meta = snapshot.metadata.get("capture_metadata") or {}
    last_error = capture_meta.get("last_error") or {}
    assert last_error.get("retryable") is True
