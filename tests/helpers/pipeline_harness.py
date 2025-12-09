"""Reusable helpers for executing ETS pipeline scenarios end-to-end."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

from unittest.mock import patch

from backend.app.domain.ef01_capture.watch_folders import (
    WATCH_SUBDIRECTORIES,
    ensure_watch_root_layout,
)
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.infra.llm_gateway import SemanticGatewayError
from backend.app.jobs import (
    extraction_worker,
    normalization_worker,
    semantic_worker,
    transcription_worker,
)
from backend.app.jobs.transcription_worker import TranscriptionOutput
from tests.helpers.logging import RecordingLogger

__all__ = [
    "PipelineHarness",
    "HarnessJobQueue",
    "DeterministicTranscriptionClient",
    "DeterministicSemanticClient",
    "FailingSemanticClient",
]


class HarnessJobQueue:
    """In-memory job queue stub used to simulate INF-02 hand-offs."""

    def __init__(self) -> None:
        self.enqueued_jobs: list[tuple[str, dict]] = []

    def enqueue(
        self, job_type: str, payload: dict
    ) -> None:  # pragma: no cover - simple stub
        self.enqueued_jobs.append((job_type, dict(payload)))

    def pop(self, job_type: str) -> dict:
        for index, (queued_type, payload) in enumerate(self.enqueued_jobs):
            if queued_type == job_type:
                self.enqueued_jobs.pop(index)
                return payload
        raise AssertionError(f"Job '{job_type}' not found in harness queue")

    def clear(self) -> None:
        self.enqueued_jobs.clear()


@dataclass
class DeterministicTranscriptionClient:
    """Stub transcription client that returns deterministic text/segments."""

    transcript_text: str = "Harness transcript sample."

    def transcribe(
        self,
        *,
        source_path: str,
        media_type: Optional[str],
        language_hint: Optional[str],
        profile: str,
    ) -> TranscriptionOutput:
        del source_path, media_type, language_hint, profile
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
                "language": "en",
                "model": "stub_whisper",
                "confidence": 0.99,
            },
        )


class DeterministicSemanticClient:
    """Stub LLM gateway client that emits predictable semantic responses."""

    def __init__(self) -> None:
        self.response = {
            "summary": "Harness summary output.",
            "display_title": "Harness Title",
            "model_used": "stub:gpt",
            "tags": ["Harness", "Pipeline"],
            "type_label": "Reference",
            "domain_label": "Engineering",
        }

    def generate_semantic_response(
        self, **_: Any
    ) -> SimpleNamespace:  # pragma: no cover - thin shim
        return SimpleNamespace(**self.response)


class FailingSemanticClient:
    """LLM client stub that always triggers a terminal SemanticGatewayError."""

    def __init__(self, code: str = "provider_unavailable") -> None:
        self.code = code

    def generate_semantic_response(self, **_: Any) -> SimpleNamespace:
        raise SemanticGatewayError(
            "semantic adapter unavailable", retryable=False, code=self.code
        )


class HarnessPatcher:
    """Context manager that mirrors pytest's monkeypatch setattr interface."""

    def __init__(self) -> None:
        self._stack = ExitStack()

    def setattr(self, target: Any, name: str, value: Any) -> None:
        self._stack.enter_context(patch.object(target, name, value))

    def close(self) -> None:
        self._stack.close()


class PipelineHarness:
    """Coordinates EF-02 → EF-05 jobs using in-memory gateways and stubs."""

    def __init__(
        self,
        work_dir: Path,
        *,
        patcher: Optional[Any] = None,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.patcher = patcher or HarnessPatcher()
        self.gateway = InMemoryEntryStoreGateway()
        self.logger = RecordingLogger()
        self.queue = HarnessJobQueue()
        self.transcription_client = DeterministicTranscriptionClient()
        self.semantic_client = DeterministicSemanticClient()
        self.last_entry_id: Optional[str] = None

        self._audio_root = ensure_watch_root_layout(self.work_dir / "audio_watch")
        self._document_root = ensure_watch_root_layout(self.work_dir / "document_watch")
        self._transcript_root = self.work_dir / "transcripts"
        self._transcript_root.mkdir(parents=True, exist_ok=True)
        self._extraction_root = self.work_dir / "extraction_outputs"
        self._extraction_root.mkdir(parents=True, exist_ok=True)
        self._segment_root = self.work_dir / "segment_cache"
        self._segment_root.mkdir(parents=True, exist_ok=True)

        self._patch_worker_state()

    def __enter__(self) -> "PipelineHarness":  # pragma: no cover - convenience helper
        return self

    def __exit__(
        self, exc_type, exc, tb
    ) -> None:  # pragma: no cover - convenience helper
        self.close()

    def close(self) -> None:
        close_fn = getattr(self.patcher, "close", None)
        if callable(close_fn):
            close_fn()

    def reset(self) -> None:
        """Clear logger + job queue to prepare for another scenario."""

        self.queue.clear()
        self.logger.records.clear()

    def run_audio_pipeline(
        self,
        *,
        correlation_id: str = "ets-audio-pipeline",
        transcription_client: Optional[Any] = None,
        semantic_client: Optional[Any] = None,
    ) -> str:
        self.reset()
        processing_path = self._stage_audio_file("ets_audio_fixture.wav")
        entry_id = self._create_audio_entry(processing_path)
        self.last_entry_id = entry_id

        transcription_worker.handle(
            {
                "entry_id": entry_id,
                "source_path": processing_path,
                "source_channel": "watch_folder_audio",
                "fingerprint": "ets-audio-fingerprint",
                "media_type": "audio/wav",
                "language_hint": "en",
                "llm_profile": "transcribe_v1",
                "correlation_id": correlation_id,
            },
            entry_gateway=self.gateway,
            transcription_client=transcription_client or self.transcription_client,
            jobqueue_adapter=self.queue,
        )

        normalization_payload = self.queue.pop("echo.normalize_entry")
        normalization_worker.handle(
            normalization_payload,
            entry_gateway=self.gateway,
            jobqueue_adapter=self.queue,
        )

        semantic_payload = self.queue.pop("echo.semantic_enrich")
        semantic_worker.handle(
            semantic_payload,
            entry_gateway=self.gateway,
            llm_client=semantic_client or self.semantic_client,
        )
        return entry_id

    def run_document_pipeline(
        self,
        *,
        correlation_id: str = "ets-document-pipeline",
        semantic_client: Optional[Any] = None,
    ) -> str:
        self.reset()
        processing_path = self._stage_document_file("ets_doc_fixture.txt")
        entry_id = self._create_document_entry(processing_path)
        self.last_entry_id = entry_id

        extraction_worker.handle(
            {
                "entry_id": entry_id,
                "source_path": processing_path,
                "source_channel": "watch_documents",
                "fingerprint": "ets-doc-fingerprint",
                "source_mime": "text/plain",
                "language_hint": "en",
                "correlation_id": correlation_id,
            },
            entry_gateway=self.gateway,
            jobqueue_adapter=self.queue,
        )

        normalization_payload = self.queue.pop("echo.normalize_entry")
        normalization_worker.handle(
            normalization_payload,
            entry_gateway=self.gateway,
            jobqueue_adapter=self.queue,
        )

        semantic_payload = self.queue.pop("echo.semantic_enrich")
        semantic_worker.handle(
            semantic_payload,
            entry_gateway=self.gateway,
            llm_client=semantic_client or self.semantic_client,
        )
        return entry_id

    def _stage_audio_file(self, filename: str) -> str:
        processing_dir = Path(self._audio_root) / WATCH_SUBDIRECTORIES[1]
        processing_dir.mkdir(parents=True, exist_ok=True)
        target = processing_dir / filename
        target.write_text("audio-bytes", encoding="utf-8")
        return str(target)

    def _stage_document_file(self, filename: str) -> str:
        processing_dir = Path(self._document_root) / WATCH_SUBDIRECTORIES[1]
        processing_dir.mkdir(parents=True, exist_ok=True)
        target = processing_dir / filename
        target.write_text(
            """EchoForge ETS document fixture.\n\nThis text validates EF-03 extraction before normalization.""",
            encoding="utf-8",
        )
        return str(target)

    def _create_audio_entry(self, source_path: str) -> str:
        record = self.gateway.create_entry(
            source_type="audio",
            source_channel="watch_folder_audio",
            source_path=source_path,
            metadata={
                "capture_fingerprint": "ets-audio-fingerprint",
                "fingerprint_algo": "sha256",
            },
            pipeline_status=PIPELINE_STATUS.QUEUED_FOR_TRANSCRIPTION,
        )
        return record.entry_id

    def _create_document_entry(self, source_path: str) -> str:
        record = self.gateway.create_entry(
            source_type="document",
            source_channel="watch_documents",
            source_path=source_path,
            metadata={
                "capture_fingerprint": "ets-doc-fingerprint",
                "fingerprint_algo": "sha256",
            },
            pipeline_status=PIPELINE_STATUS.QUEUED_FOR_EXTRACTION,
        )
        return record.entry_id

    def _patch_worker_state(self) -> None:
        for module in (
            transcription_worker,
            extraction_worker,
            normalization_worker,
            semantic_worker,
        ):
            self.patcher.setattr(module, "logger", self.logger)

        self.patcher.setattr(
            transcription_worker,
            "_TRANSCRIPT_OUTPUT_ROOT",
            str(self._transcript_root),
        )
        self.patcher.setattr(transcription_worker, "_TRANSCRIPT_PUBLIC_BASE_URL", None)

        self.patcher.setattr(extraction_worker, "_PROCESSED_ROOT", None)
        self.patcher.setattr(extraction_worker, "_FAILED_ROOT", None)
        self.patcher.setattr(
            extraction_worker,
            "_EXTRACTION_OUTPUT_ROOT",
            str(self._extraction_root),
        )
        self.patcher.setattr(extraction_worker, "_EXTRACTION_PUBLIC_BASE_URL", None)
        self.patcher.setattr(
            extraction_worker,
            "_SEGMENT_CACHE_ROOT",
            str(self._segment_root),
        )
        self.patcher.setattr(extraction_worker, "_SEGMENT_CACHE_THRESHOLD", 1_000_000)

        base_profile = {
            "max_input_chars": 100_000,
            "max_output_chars": 80_000,
            "remove_timestamps": True,
            "emit_segments": True,
            "segment_threshold_chars": 200,
            "preserve_markdown": False,
            "sentence_case_all_caps": False,
        }
        self.patcher.setattr(normalization_worker, "_BASE_PROFILE", base_profile.copy())
        self.patcher.setattr(normalization_worker, "_PROFILES", {})
        self.patcher.setattr(normalization_worker, "_DEFAULT_PROFILE", "standard")
        self.patcher.setattr(normalization_worker, "_WORKER_ID", "ef04::ets")

        summary_config: Dict[str, Any] = {
            "max_preview_chars": 200,
            "max_deep_chars": 600,
            "max_retry_attempts": 2,
            "retry_backoff_ms": 0,
        }
        self.patcher.setattr(semantic_worker, "_SUMMARY_CONFIG", summary_config)
        self.patcher.setattr(semantic_worker, "_SUMMARY_PROFILE", "echo_summary_v1")
        self.patcher.setattr(semantic_worker, "_CLASSIFY_PROFILE", "echo_classify_v1")
