"""EF-03 document extraction worker implementation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple
from urllib.parse import urljoin

from backend.app.config import load_settings
from backend.app.config.loader import DEFAULT_DOCUMENT_CONFIG
from backend.app.domain.ef01_capture.watch_folders import WATCH_SUBDIRECTORIES
from backend.app.domain.ef03_extraction import (
    DocumentExtractionError,
    extract_document,
)
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.infra import jobqueue
from backend.app.infra.logging import get_logger

logger = get_logger(__name__)

_SETTINGS = load_settings()
_DOCUMENT_CFG = _SETTINGS.echo.get("documents") or {}
_PROCESSED_ROOT = _DOCUMENT_CFG.get("processed_root")
_FAILED_ROOT = _DOCUMENT_CFG.get("failed_root")
_PREVIEW_LIMIT = int(_DOCUMENT_CFG.get("preview_limit", 400))
_EXTRACTION_OUTPUT_ROOT = (
    _DOCUMENT_CFG.get("extraction_output_root")
    or DEFAULT_DOCUMENT_CONFIG["extraction_output_root"]
)
_EXTRACTION_PUBLIC_BASE_URL = _DOCUMENT_CFG.get("extraction_public_base_url")
_SEGMENT_CACHE_ROOT = _DOCUMENT_CFG.get("segment_cache_root")
_SEGMENT_CACHE_THRESHOLD = int(
    _DOCUMENT_CFG.get(
        "segment_cache_threshold_bytes",
        DEFAULT_DOCUMENT_CONFIG["segment_cache_threshold_bytes"],
    )
)
_MAX_INLINE_CHARS = int(
    _DOCUMENT_CFG.get(
        "max_inline_chars",
        DEFAULT_DOCUMENT_CONFIG["max_inline_chars"],
    )
)
_WORKER_ID = _DOCUMENT_CFG.get(
    "worker_id", f"ef03_extraction::{_SETTINGS.runtime_shape}"
)


class EntryExtractionStore(Protocol):
    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str): ...

    def record_extraction_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[list[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]],
        verbatim_path: Optional[str],
        verbatim_preview: Optional[str],
        content_lang: Optional[str],
    ): ...

    def record_extraction_failure(
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
    ) -> None: ...


class JobQueueAdapter(Protocol):
    def enqueue(self, job_type: str, payload: Dict[str, Any]) -> None: ...


_ENTRY_STORE: Optional[EntryExtractionStore] = None


def _get_default_entry_store() -> EntryExtractionStore:
    global _ENTRY_STORE
    if _ENTRY_STORE is None:
        _ENTRY_STORE = build_entry_store_gateway(fallback_to_memory=True)
    return _ENTRY_STORE


def handle(
    payload: dict,
    *,
    entry_gateway: Optional[EntryExtractionStore] = None,
    jobqueue_adapter: Optional[JobQueueAdapter] = None,
) -> None:
    gateway = entry_gateway or _get_default_entry_store()
    queue = jobqueue_adapter or jobqueue

    entry_id = payload.get("entry_id")
    source_path = payload.get("source_path")
    source_channel = payload.get("source_channel")
    fingerprint = payload.get("fingerprint")

    if not entry_id or not source_path or not source_channel or not fingerprint:
        raise ValueError("extraction payload missing required fields")

    source_mime = payload.get("source_mime")
    page_range = payload.get("page_range")
    ocr_mode = payload.get("ocr_mode", "auto")
    metadata_overrides = payload.get("metadata_overrides")
    correlation_id = payload.get("correlation_id")
    language_hint = payload.get("language_hint")
    inline_char_limit = _determine_inline_char_limit(metadata_overrides)

    start_clock = time.perf_counter()
    logger.info(
        "extraction_started",
        extra={
            "entry_id": entry_id,
            "source_channel": source_channel,
            "correlation_id": correlation_id,
            "source_path": source_path,
            "fingerprint": fingerprint,
            "source_mime": source_mime,
            "stage": "extraction",
            "pipeline_status": PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
        },
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="extraction_started",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_IN_PROGRESS,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={
            "source_path": source_path,
            "fingerprint": fingerprint,
            "source_mime": source_mime,
            "page_range": page_range,
            "ocr_mode": ocr_mode,
        },
    )
    document_patch = _compact_dict(
        {
            "source_path": source_path,
            "source_channel": source_channel,
            "source_mime": source_mime,
            "page_range": page_range,
            "ocr_mode": ocr_mode,
            "fingerprint": fingerprint,
        }
    )
    capture_patch: Dict[str, Any] = {}
    if document_patch:
        capture_patch["document"] = document_patch
    _merge_capture_metadata_patch(gateway, entry_id, capture_patch)

    verbatim_file: Optional[Path] = None
    inline_text: Optional[str] = None
    truncation_metadata: Optional[Dict[str, Any]] = None

    try:
        result = extract_document(
            source_path,
            mime_type=source_mime,
            page_range=page_range,
            ocr_mode=ocr_mode,
            metadata_overrides=metadata_overrides,
        )
        verbatim_file = _persist_extraction_artifact(entry_id, result.text)
        inline_text, truncation_metadata = _prepare_inline_text(
            result.text,
            inline_char_limit=inline_char_limit,
        )
        processing_ms = _elapsed_ms(start_clock)
    except DocumentExtractionError as exc:
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

    if inline_text is None:  # pragma: no cover - defensive guard
        inline_text = result.text

    metadata = dict(result.metadata or {})
    segment_count = len(result.segments or [])
    metadata.update(
        {
            "processing_ms": processing_ms,
            "worker_id": _WORKER_ID,
            "source_mime": source_mime,
            "ocr_mode": ocr_mode,
            "page_range": page_range,
            "segment_count": segment_count,
        }
    )
    if truncation_metadata:
        metadata.update(truncation_metadata)
    segments_to_store = result.segments
    segment_cache_path: Optional[Path] = None
    if result.segments:
        segments_to_store, segment_cache_path, cached_bytes = _maybe_cache_segments(
            entry_id,
            result.segments,
        )
        if segment_cache_path:
            metadata["segment_cache_path"] = str(segment_cache_path)
            metadata["segment_cache_bytes"] = cached_bytes
            logger.info(
                "extraction_segments_cached",
                extra={
                    "entry_id": entry_id,
                    "path": str(segment_cache_path),
                    "byte_length": cached_bytes,
                    "correlation_id": correlation_id,
                },
            )
    if verbatim_file:
        metadata["extracted_text_file_path"] = str(verbatim_file)
    verbatim_preview = _build_preview(inline_text)
    verbatim_path = _build_verbatim_reference(verbatim_file)
    content_lang = language_hint or metadata.get("language")

    success_doc_patch = _compact_dict(
        {
            "verbatim_path": verbatim_path,
            "page_count": metadata.get("page_count"),
            "segment_count": segment_count,
            "char_count": metadata.get("char_count"),
            "segment_cache_path": metadata.get("segment_cache_path"),
            "extracted_text_file_path": metadata.get("extracted_text_file_path"),
        }
    )
    success_patch: Dict[str, Any] = {}
    if success_doc_patch:
        success_patch["document"] = success_doc_patch
    _merge_capture_metadata_patch(gateway, entry_id, success_patch)

    gateway.record_extraction_result(
        entry_id,
        text=inline_text,
        segments=segments_to_store,
        metadata=metadata,
        verbatim_path=verbatim_path,
        verbatim_preview=verbatim_preview,
        content_lang=content_lang,
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.EXTRACTION_COMPLETE,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="extraction_completed",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_COMPLETE,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={
            "processing_ms": processing_ms,
            "segment_count": len(result.segments or []),
        },
    )

    destination = _move_document_file(
        source_path,
        target="processed",
        source_channel=source_channel,
        correlation_id=correlation_id,
    )
    if destination:
        _record_capture_event(
            gateway,
            entry_id,
            event_type="extraction_file_rolled",
            pipeline_status=PIPELINE_STATUS.EXTRACTION_COMPLETE,
            correlation_id=correlation_id,
            source_channel=source_channel,
            extra={
                "destination_path": destination,
                "target_stage": "processed",
            },
        )
        _merge_capture_metadata_patch(
            gateway,
            entry_id,
            {"document": {"processed_path": destination}},
        )

    queue.enqueue(
        "echo.normalize_entry",
        {
            "entry_id": entry_id,
            "source": "document_extraction",
            "chunk_count": segment_count,
            "content_lang": content_lang,
            "correlation_id": correlation_id,
        },
    )
    logger.info(
        "extraction_completed",
        extra={
            "entry_id": entry_id,
            "source_channel": source_channel,
            "correlation_id": correlation_id,
            "stage": "extraction",
            "pipeline_status": PIPELINE_STATUS.EXTRACTION_COMPLETE,
            "processing_ms": processing_ms,
            "segment_count": segment_count,
        },
    )


def _handle_failure(
    gateway: EntryExtractionStore,
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
    gateway.record_extraction_failure(
        entry_id,
        error_code=error_code,
        message=message,
        retryable=retryable,
    )
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.EXTRACTION_FAILED,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="extraction_failed",
        pipeline_status=PIPELINE_STATUS.EXTRACTION_FAILED,
        correlation_id=correlation_id,
        source_channel=source_channel,
        extra={
            "error_code": error_code,
            "retryable": retryable,
            "processing_ms": processing_ms,
        },
    )
    destination = _move_document_file(
        source_path,
        target="failed",
        source_channel=source_channel,
        correlation_id=correlation_id,
    )
    if destination:
        _record_capture_event(
            gateway,
            entry_id,
            event_type="extraction_file_rolled",
            pipeline_status=PIPELINE_STATUS.EXTRACTION_FAILED,
            correlation_id=correlation_id,
            source_channel=source_channel,
            extra={
                "destination_path": destination,
                "target_stage": "failed",
            },
        )
    failure_patch: Dict[str, Any] = {
        "last_error": {
            "stage": "extraction",
            "code": error_code,
            "retryable": retryable,
        },
    }
    if destination:
        failure_patch["document"] = {"failed_path": destination}
    _merge_capture_metadata_patch(gateway, entry_id, failure_patch)
    logger.exception(
        "extraction_failed",
        extra={
            "entry_id": entry_id,
            "error_code": error_code,
            "retryable": retryable,
            "correlation_id": correlation_id,
            "stage": "extraction",
            "pipeline_status": PIPELINE_STATUS.EXTRACTION_FAILED,
            "processing_ms": processing_ms,
        },
    )


def _record_capture_event(
    gateway: EntryExtractionStore,
    entry_id: str,
    *,
    event_type: str,
    pipeline_status: str,
    correlation_id: Optional[str],
    source_channel: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    data: Dict[str, Any] = {
        "stage": "extraction",
        "pipeline_status": pipeline_status,
        "source_channel": source_channel,
    }
    if correlation_id:
        data["correlation_id"] = correlation_id
    if extra:
        data.update(extra)
    try:
        gateway.record_capture_event(entry_id, event_type=event_type, data=data)
    except AttributeError:
        logger.debug(
            "capture_event_not_supported",
            extra={"entry_id": entry_id, "event_type": event_type},
        )


def _move_document_file(
    source_path: str,
    *,
    target: str,
    source_channel: str,
    correlation_id: Optional[str],
) -> Optional[str]:
    source = Path(source_path)
    if not source.exists():
        return None
    if target not in {"processed", "failed"}:
        return None

    configured_root = _PROCESSED_ROOT if target == "processed" else _FAILED_ROOT
    if configured_root:
        destination_dir = Path(configured_root).expanduser()
    else:
        parent = source.parent
        if parent.name != WATCH_SUBDIRECTORIES[1]:
            return None
        root = parent.parent
        destination_dir = root / (
            WATCH_SUBDIRECTORIES[2]
            if target == "processed"
            else WATCH_SUBDIRECTORIES[3]
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    if destination.exists():
        destination.unlink()
    try:
        shutil.move(str(source), destination)
    except FileNotFoundError:
        return None

    logger.info(
        "extraction_file_moved",
        extra={
            "source": str(source),
            "destination": str(destination),
            "target_folder": target,
            "correlation_id": correlation_id,
            "source_channel": source_channel,
        },
    )
    return str(destination)


def _persist_extraction_artifact(entry_id: str, text: str) -> Path:
    root = _resolve_extraction_root()
    target = root / f"{entry_id}.txt"
    _atomic_write_text(target, text)
    return target


def _maybe_cache_segments(
    entry_id: str,
    segments: list[Dict[str, Any]],
) -> Tuple[Optional[list[Dict[str, Any]]], Optional[Path], Optional[int]]:
    if not segments or not _SEGMENT_CACHE_ROOT or _SEGMENT_CACHE_THRESHOLD <= 0:
        return segments, None, None
    serialized = json.dumps(segments, ensure_ascii=False, indent=2)
    byte_length = len(serialized.encode("utf-8"))
    if byte_length <= _SEGMENT_CACHE_THRESHOLD:
        return segments, None, None
    root = _resolve_segment_cache_root()
    target = root / f"{entry_id}.segments.json"
    _atomic_write_text(target, serialized)
    return None, target, byte_length


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
    if _EXTRACTION_PUBLIC_BASE_URL:
        base = _EXTRACTION_PUBLIC_BASE_URL.rstrip("/") + "/"
        try:
            relative = path.relative_to(_resolve_extraction_root()).as_posix()
        except ValueError:
            relative = path.name
        return urljoin(base, relative)
    return str(path)


def _resolve_extraction_root() -> Path:
    if not _EXTRACTION_OUTPUT_ROOT:
        raise RuntimeError("extraction_output_root is not configured")
    return Path(_EXTRACTION_OUTPUT_ROOT).expanduser()


def _resolve_segment_cache_root() -> Path:
    if not _SEGMENT_CACHE_ROOT:
        raise RuntimeError("segment_cache_root is not configured")
    return Path(_SEGMENT_CACHE_ROOT).expanduser()


def _build_preview(text: str, limit: int = _PREVIEW_LIMIT) -> Optional[str]:
    normalized = text.strip()
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _elapsed_ms(start_clock: float) -> int:
    return max(0, int((time.perf_counter() - start_clock) * 1000))


def _compact_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _merge_capture_metadata_patch(
    gateway: EntryExtractionStore,
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


def _determine_inline_char_limit(
    metadata_overrides: Optional[Dict[str, Any]],
) -> Optional[int]:
    if metadata_overrides and isinstance(metadata_overrides, dict):
        override_value = metadata_overrides.get("max_inline_chars")
        try:
            parsed = int(override_value)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None and parsed > 0:
            return parsed
    if _MAX_INLINE_CHARS <= 0:
        return None
    return _MAX_INLINE_CHARS


def _prepare_inline_text(
    text: str,
    *,
    inline_char_limit: Optional[int],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    if inline_char_limit is None or inline_char_limit <= 0:
        return text, None
    if len(text) <= inline_char_limit:
        return text, None
    truncated_text = text[:inline_char_limit]
    metadata = {
        "truncated": True,
        "inline_char_limit": inline_char_limit,
        "extracted_char_count": len(text),
    }
    return truncated_text, metadata
