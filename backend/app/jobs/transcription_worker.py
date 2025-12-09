"""EF-02 transcription worker implementation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple
from urllib.parse import urljoin

from backend.app.config import DEFAULT_WHISPER_CONFIG, load_settings
from backend.app.domain.ef01_capture.watch_folders import WATCH_SUBDIRECTORIES
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.infra import jobqueue
from backend.app.infra.llm_gateway import TranscriptionGatewayError, transcribe_audio
from backend.app.infra.logging import get_logger

logger = get_logger(__name__)


_SETTINGS = load_settings()
_WHISPER_CONFIG = _SETTINGS.llm.get("whisper") or {}
_TRANSCRIPT_OUTPUT_ROOT = _WHISPER_CONFIG.get(
    "transcript_output_root", DEFAULT_WHISPER_CONFIG["transcript_output_root"]
)
_TRANSCRIPT_PUBLIC_BASE_URL = _WHISPER_CONFIG.get("transcript_public_base_url")
_VERBATIM_PREVIEW_LIMIT = 400


class EntryTranscriptionStore(Protocol):
    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str): ...

    def record_transcription_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ): ...

    def record_transcription_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ): ...

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ): ...

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Any: ...


class JobQueueAdapter(Protocol):
    def enqueue(self, job_type: str, payload: Dict[str, Any]) -> None: ...


class TranscriptionClient(Protocol):
    def transcribe(
        self,
        *,
        source_path: str,
        media_type: Optional[str],
        language_hint: Optional[str],
        profile: str,
    ) -> "TranscriptionOutput": ...


@dataclass
class TranscriptionOutput:
    text: str
    segments: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class TranscriptionError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, code: str = "internal_error"
    ):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class LlmGatewayTranscriptionClient:
    def transcribe(
        self,
        *,
        source_path: str,
        media_type: Optional[str],
        language_hint: Optional[str],
        profile: str,
    ) -> TranscriptionOutput:
        try:
            response = transcribe_audio(
                source_path,
                language_hint=language_hint,
                profile=profile,
            )
        except TranscriptionGatewayError as exc:
            raise TranscriptionError(
                str(exc), retryable=exc.retryable, code=exc.code
            ) from exc
        segments = _normalize_segments(response.get("segments"))
        return TranscriptionOutput(
            text=response["text"],
            segments=segments,
            metadata={
                "language": response.get("language"),
                "confidence": response.get("confidence"),
                "model": response.get("model"),
                "duration_ms": response.get("duration_ms"),
                "media_type": media_type,
            },
        )


_ENTRY_STORE: Optional[EntryTranscriptionStore] = None
_TRANSCRIPTION_CLIENT = LlmGatewayTranscriptionClient()


def _get_default_entry_store() -> EntryTranscriptionStore:
    global _ENTRY_STORE
    if _ENTRY_STORE is None:
        _ENTRY_STORE = build_entry_store_gateway(fallback_to_memory=True)
    return _ENTRY_STORE


def handle(
    payload: dict,
    *,
    entry_gateway: Optional[EntryTranscriptionStore] = None,
    transcription_client: Optional[TranscriptionClient] = None,
    jobqueue_adapter: Optional[JobQueueAdapter] = None,
) -> None:
    """Process a transcription job payload emitted by EF-01/INF-02."""

    gateway = entry_gateway or _get_default_entry_store()
    client = transcription_client or _TRANSCRIPTION_CLIENT
    queue = jobqueue_adapter or jobqueue

    entry_id = payload.get("entry_id")
    source_path = payload.get("source_path")
    source_channel = payload.get("source_channel")
    fingerprint = payload.get("fingerprint")

    if not entry_id or not source_path or not source_channel or not fingerprint:
        raise ValueError("transcription payload missing required fields")

    media_type = payload.get("media_type")
    language_hint = payload.get("language_hint")
    profile = payload.get("llm_profile", "transcribe_v1")
    correlation_id = payload.get("correlation_id")
    start_clock = time.perf_counter()

    logger.info(
        "transcription_started",
        extra={
            "entry_id": entry_id,
            "source_channel": source_channel,
            "fingerprint": fingerprint,
            "correlation_id": correlation_id,
            "source_path": source_path,
            "stage": "transcription",
            "pipeline_status": PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
        },
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="transcription_started",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_IN_PROGRESS,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={"source_path": source_path},
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "transcription": {
                "source_path": source_path,
                "source_channel": source_channel,
                "fingerprint": fingerprint,
                "profile": profile,
                "language_hint": language_hint,
                "media_type": media_type,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    transcript_file: Optional[Path] = None
    segments_file: Optional[Path] = None

    try:
        result = client.transcribe(
            source_path=source_path,
            media_type=media_type,
            language_hint=language_hint,
            profile=profile,
        )
        transcript_file, segments_file = _persist_transcript_artifacts(
            entry_id,
            result.text,
            result.segments,
        )
        processing_ms = _elapsed_ms(start_clock)
    except TranscriptionError as exc:
        processing_ms = _elapsed_ms(start_clock)
        _handle_failure(
            gateway,
            entry_id,
            error_code=exc.code,
            message=str(exc),
            retryable=exc.retryable,
            correlation_id=correlation_id,
            source_channel=source_channel,
            source_path=source_path,
            processing_ms=processing_ms,
        )
        raise
    except Exception as exc:  # pragma: no cover - defensive path
        processing_ms = _elapsed_ms(start_clock)
        _handle_failure(
            gateway,
            entry_id,
            error_code="internal_error",
            message=str(exc),
            retryable=False,
            correlation_id=correlation_id,
            source_channel=source_channel,
            source_path=source_path,
            processing_ms=processing_ms,
        )
        raise

    metadata = dict(result.metadata or {})
    if media_type and "media_type" not in metadata:
        metadata["media_type"] = media_type
    metadata["processing_ms"] = processing_ms
    if transcript_file:
        metadata["transcript_file_path"] = str(transcript_file)
    if segments_file:
        metadata["transcript_segments_path"] = str(segments_file)

    verbatim_path = _build_verbatim_reference(transcript_file)
    verbatim_preview = _build_verbatim_preview(result.text)
    content_lang = metadata.get("language")

    segment_count = len(result.segments or [])

    gateway.record_transcription_result(
        entry_id,
        text=result.text,
        segments=result.segments,
        metadata=metadata,
        verbatim_path=verbatim_path,
        verbatim_preview=verbatim_preview,
        content_lang=content_lang,
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="transcription_completed",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={
            "processing_ms": processing_ms,
            "segment_count": segment_count,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "transcription": {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "processing_ms": processing_ms,
                "segment_count": len(result.segments or []),
                "transcript_file_path": str(transcript_file)
                if transcript_file
                else None,
                "segments_file_path": str(segments_file) if segments_file else None,
                "content_lang": content_lang,
            }
        },
    )

    destination = _move_media_file(
        source_path,
        target_folder=WATCH_SUBDIRECTORIES[2],
        source_channel=source_channel,
        correlation_id=correlation_id,
    )
    if destination:
        _record_capture_event(
            gateway,
            entry_id,
            event_type="transcription_file_rolled",
            pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
            correlation_id=correlation_id,
            source_channel=source_channel,
            extra={
                "destination_path": destination,
                "target_stage": WATCH_SUBDIRECTORIES[2],
            },
        )

    queue.enqueue(
        "echo.normalize_entry",
        {
            "entry_id": entry_id,
            "source": "transcription",
            "correlation_id": correlation_id,
        },
    )
    logger.info(
        "transcription_completed",
        extra={
            "entry_id": entry_id,
            "source_channel": source_channel,
            "correlation_id": correlation_id,
            "processing_ms": processing_ms,
            "segment_count": segment_count,
            "stage": "transcription",
            "pipeline_status": PIPELINE_STATUS.TRANSCRIPTION_COMPLETE,
        },
    )


def _handle_failure(
    gateway: EntryTranscriptionStore,
    entry_id: str,
    *,
    error_code: str,
    message: str,
    retryable: bool,
    correlation_id: Optional[str],
    source_channel: str,
    source_path: str,
    processing_ms: int,
) -> None:
    gateway.record_transcription_failure(
        entry_id,
        error_code=error_code,
        message=message,
        retryable=retryable,
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_FAILED,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="transcription_failed",
        pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_FAILED,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={
            "error_code": error_code,
            "retryable": retryable,
            "processing_ms": processing_ms,
        },
    )
    destination = _move_media_file(
        source_path,
        target_folder=WATCH_SUBDIRECTORIES[3],
        source_channel=source_channel,
        correlation_id=correlation_id,
    )
    if destination:
        _record_capture_event(
            gateway,
            entry_id,
            event_type="transcription_file_rolled",
            pipeline_status=PIPELINE_STATUS.TRANSCRIPTION_FAILED,
            correlation_id=correlation_id,
            source_channel=source_channel,
            extra={
                "destination_path": destination,
                "target_stage": WATCH_SUBDIRECTORIES[3],
            },
        )
    logger.exception(
        "transcription_failed",
        extra={
            "entry_id": entry_id,
            "error_code": error_code,
            "retryable": retryable,
            "correlation_id": correlation_id,
            "source_channel": source_channel,
            "stage": "transcription",
            "pipeline_status": PIPELINE_STATUS.TRANSCRIPTION_FAILED,
            "processing_ms": processing_ms,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "last_error": {
                "stage": "transcription",
                "code": error_code,
                "retryable": retryable,
            }
        },
    )


def _persist_transcript_artifacts(
    entry_id: str,
    transcript_text: str,
    segments: Optional[List[Dict[str, Any]]],
) -> Tuple[Path, Optional[Path]]:
    root = _resolve_transcript_root()
    transcript_path = root / f"{entry_id}.txt"
    _atomic_write_text(transcript_path, transcript_text)

    segments_path: Optional[Path] = None
    if segments:
        segments_path = root / f"{entry_id}.segments.json"
        serialized = json.dumps(segments, ensure_ascii=False, indent=2)
        _atomic_write_text(segments_path, serialized)

    return transcript_path, segments_path


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(target.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _build_verbatim_reference(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    if _TRANSCRIPT_PUBLIC_BASE_URL:
        base = _TRANSCRIPT_PUBLIC_BASE_URL.rstrip("/") + "/"
        try:
            relative = path.relative_to(_resolve_transcript_root()).as_posix()
        except ValueError:
            relative = path.name
        return urljoin(base, relative)
    return str(path)


def _build_verbatim_preview(
    text: str, limit: int = _VERBATIM_PREVIEW_LIMIT
) -> Optional[str]:
    normalized = text.strip()
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _resolve_transcript_root() -> Path:
    if not _TRANSCRIPT_OUTPUT_ROOT:
        raise RuntimeError("transcript_output_root is not configured")
    return Path(_TRANSCRIPT_OUTPUT_ROOT).expanduser()


def _normalize_segments(
    raw_segments: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    if not raw_segments:
        return None
    normalized: List[Dict[str, Any]] = []
    for segment in raw_segments:
        normalized.append(
            {
                "text": str(segment.get("text", "")).strip(),
                "start_ms": _seconds_to_ms(segment.get("start")),
                "end_ms": _seconds_to_ms(segment.get("end")),
                "tokens": list(segment.get("tokens") or []),
            }
        )
    return normalized


def _seconds_to_ms(value: Optional[float]) -> int:
    if value is None:
        return 0
    try:
        return max(0, int(round(float(value) * 1000)))
    except (TypeError, ValueError):
        return 0


def _record_capture_event(
    gateway: EntryTranscriptionStore,
    entry_id: str,
    *,
    event_type: str,
    pipeline_status: str,
    correlation_id: Optional[str],
    source_channel: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    data: Dict[str, Any] = {
        "stage": "transcription",
        "pipeline_status": pipeline_status,
        "source_channel": source_channel,
    }
    if correlation_id:
        data["correlation_id"] = correlation_id
    if extra:
        data.update(extra)
    try:
        gateway.record_capture_event(
            entry_id,
            event_type=event_type,
            data=data,
        )
    except AttributeError:
        # Gateways that do not support capture events should not break the worker.
        logger.debug(
            "capture_event_not_supported",
            extra={"entry_id": entry_id, "event_type": event_type},
        )


def _merge_capture_metadata_patch(
    gateway: EntryTranscriptionStore,
    entry_id: str,
    patch: Optional[Dict[str, Any]],
) -> None:
    if not patch:
        return
    try:
        gateway.merge_capture_metadata(entry_id, patch=patch)
    except AttributeError:
        logger.debug(
            "capture_metadata_merge_not_supported",
            extra={"entry_id": entry_id},
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "capture_metadata_merge_failed",
            extra={"entry_id": entry_id},
        )


def _move_media_file(
    source_path: str,
    *,
    target_folder: str,
    source_channel: str,
    correlation_id: Optional[str],
) -> Optional[str]:
    source = Path(source_path)
    if not source.exists():
        return None
    parent = source.parent
    if parent.name != WATCH_SUBDIRECTORIES[1]:
        return None
    root = parent.parent
    destination_dir = root / target_folder
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    if destination.exists():
        destination.unlink()
    try:
        shutil.move(str(source), destination)
    except FileNotFoundError:
        return None
    logger.info(
        "transcription_file_moved",
        extra={
            "source": str(source),
            "destination": str(destination),
            "target_folder": target_folder,
            "correlation_id": correlation_id,
            "source_channel": source_channel,
        },
    )
    return str(destination)


def _elapsed_ms(start_clock: float) -> int:
    return max(0, int((time.perf_counter() - start_clock) * 1000))
