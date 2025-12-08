"""EF-04 normalization worker implementation."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from backend.app.config import load_settings
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway
from backend.app.infra import jobqueue
from backend.app.infra.logging import get_logger

logger = get_logger(__name__)

_SETTINGS = load_settings()
_NORMALIZATION_CONFIG: Dict[str, Any] = dict(_SETTINGS.echo.get("normalization") or {})
_PROFILES: Dict[str, Any] = dict(_NORMALIZATION_CONFIG.get("profiles") or {})
_BASE_PROFILE: Dict[str, Any] = {
    key: value
    for key, value in _NORMALIZATION_CONFIG.items()
    if key not in {"profiles"}
}
_DEFAULT_PROFILE = _NORMALIZATION_CONFIG.get("default_profile", "standard")
_WORKER_ID = (
    _NORMALIZATION_CONFIG.get("worker_id")
    or f"ef04_normalization::{_SETTINGS.runtime_shape}"
)
for _reserved in ("worker_id", "default_profile"):
    _BASE_PROFILE.pop(_reserved, None)

_SUPPORTED_SOURCES = {"transcription", "document_extraction"}
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TIMESTAMP_RE = re.compile(
    r"^\s*(?:\[\d{1,2}:\d{2}(?::\d{2})?\]|\(\d{1,2}:\d{2}\))\s*",
    re.MULTILINE,
)
_SPEAKER_RE = re.compile(r"^(speaker\s*\d+:)\s*", re.IGNORECASE | re.MULTILINE)
_BULLET_REPLACEMENTS = {
    "•": "- ",
    "·": "- ",
    "–": "- ",
    "—": "- ",
    "*": "- ",
}


class EntryNormalizationStore(Protocol):
    def update_pipeline_status(
        self, entry_id: str, *, pipeline_status: str
    ) -> None: ...

    def record_normalization_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]],
    ) -> Any: ...

    def record_normalization_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> Any: ...

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Any: ...

    def get_entry(self, entry_id: str) -> Any: ...


class JobQueueAdapter(Protocol):
    def enqueue(self, job_type: str, payload: Dict[str, Any]) -> None: ...


class NormalizationError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


_ENTRY_STORE: Optional[EntryNormalizationStore] = None


def _get_default_entry_store() -> EntryNormalizationStore:
    global _ENTRY_STORE
    if _ENTRY_STORE is None:
        _ENTRY_STORE = build_entry_store_gateway(fallback_to_memory=True)
    return _ENTRY_STORE


def handle(
    payload: dict,
    *,
    entry_gateway: Optional[EntryNormalizationStore] = None,
    jobqueue_adapter: Optional[JobQueueAdapter] = None,
) -> None:
    gateway = entry_gateway or _get_default_entry_store()
    queue = jobqueue_adapter or jobqueue

    entry_id = payload.get("entry_id")
    source = payload.get("source")
    if not entry_id or source not in _SUPPORTED_SOURCES:
        raise ValueError("normalization payload missing required fields")

    correlation_id = payload.get("correlation_id")
    content_lang_override = payload.get("content_lang")
    chunk_count_hint = payload.get("chunk_count")
    profile_override = payload.get("normalization_profile")
    overrides = (
        payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
    )

    gateway.update_pipeline_status(
        entry_id, pipeline_status="normalization_in_progress"
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="normalization_started",
        pipeline_status="normalization_in_progress",
        correlation_id=correlation_id,
        extra={"source": source, "profile": profile_override or _DEFAULT_PROFILE},
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {"ingest_state": "processing_normalization"},
    )

    entry = gateway.get_entry(entry_id)
    raw_text: Optional[str]
    source_field: str
    if source == "transcription":
        raw_text = getattr(entry, "transcription_text", None)
        source_field = "transcription_text"
    else:
        raw_text = getattr(entry, "extracted_text", None)
        source_field = "extracted_text"
    if not raw_text:
        error = NormalizationError(
            "raw text is missing", code="raw_text_missing", retryable=False
        )
        _handle_failure(
            gateway,
            entry_id,
            error=error,
            correlation_id=correlation_id,
            source=source,
        )
        raise error

    profile_name, profile_config = _resolve_profile(profile_override)
    effective_config = dict(profile_config)
    for key, value in overrides.items():
        if value is None:
            continue
        effective_config[key] = value

    start_clock = time.perf_counter()
    try:
        normalized_text, segments, norm_meta = _normalize_text(
            raw_text,
            config=effective_config,
            overrides=overrides,
            source_field=source_field,
            chunk_count_hint=chunk_count_hint,
            worker_id=_WORKER_ID,
            profile_name=profile_name,
        )
    except NormalizationError as exc:
        _handle_failure(
            gateway,
            entry_id,
            error=exc,
            correlation_id=correlation_id,
            source=source,
        )
        raise
    except Exception as exc:  # pragma: no cover - defensive
        wrapped = NormalizationError(
            str(exc), code="normalization_internal_error", retryable=False
        )
        _handle_failure(
            gateway,
            entry_id,
            error=wrapped,
            correlation_id=correlation_id,
            source=source,
        )
        raise

    processing_ms = _elapsed_ms(start_clock)
    norm_meta["processing_ms"] = processing_ms

    gateway.record_normalization_result(
        entry_id,
        text=normalized_text,
        segments=segments,
        metadata=norm_meta,
    )
    gateway.update_pipeline_status(entry_id, pipeline_status="normalization_complete")
    segment_count = len(segments or [])
    _record_capture_event(
        gateway,
        entry_id,
        event_type="normalization_completed",
        pipeline_status="normalization_complete",
        correlation_id=correlation_id,
        extra={
            "normalized_char_count": len(normalized_text),
            "segment_count": segment_count,
            "profile": profile_name,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "ingest_state": "processing_semantics",
            "normalization": {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "normalized_char_count": len(normalized_text),
                "segment_count": segment_count,
                "profile": profile_name,
            },
        },
    )

    queue.enqueue(
        "echo.semantic_enrich",
        {
            "entry_id": entry_id,
            "source": "normalization",
            "content_lang": content_lang_override
            or getattr(entry, "content_lang", None),
            "chunk_count": norm_meta.get("chunk_count", segment_count),
            "correlation_id": correlation_id,
        },
    )


def _handle_failure(
    gateway: EntryNormalizationStore,
    entry_id: str,
    *,
    error: NormalizationError,
    correlation_id: Optional[str],
    source: str,
) -> None:
    gateway.record_normalization_failure(
        entry_id,
        error_code=error.code,
        message=str(error),
        retryable=error.retryable,
    )
    gateway.update_pipeline_status(entry_id, pipeline_status="normalization_failed")
    _record_capture_event(
        gateway,
        entry_id,
        event_type="normalization_failed",
        pipeline_status="normalization_failed",
        correlation_id=correlation_id,
        extra={
            "error_code": error.code,
            "retryable": error.retryable,
            "source": source,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "ingest_state": "failed",
            "last_error": {
                "stage": "normalization",
                "code": error.code,
                "retryable": error.retryable,
            },
        },
    )


def _normalize_text(
    raw_text: str,
    *,
    config: Dict[str, Any],
    overrides: Dict[str, Any],
    source_field: str,
    chunk_count_hint: Optional[int],
    worker_id: str,
    profile_name: str,
) -> Tuple[str, Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    text = raw_text
    applied_rules: List[str] = []
    timings: List[Dict[str, Any]] = []

    metadata: Dict[str, Any] = {
        "raw_source": source_field,
        "input_char_count": len(raw_text),
        "profile": profile_name,
        "worker_id": worker_id,
    }
    if overrides:
        metadata["overrides_applied"] = sorted(overrides.keys())

    max_input = int(config.get("max_input_chars", 0) or 0)
    if max_input > 0 and len(text) > max_input:
        metadata["input_truncated"] = True
        metadata["input_truncated_char_delta"] = len(text) - max_input
        text = text[:max_input]

    def _apply(name: str, func) -> None:
        nonlocal text
        start = time.perf_counter()
        new_text, changed = func(text)
        elapsed = _elapsed_ms(start)
        timings.append({"stage": name, "ms": elapsed})
        if changed:
            applied_rules.append(name)
            text = new_text

    _apply("strip_controls", _strip_controls_and_bom)
    _apply("normalize_newlines", _normalize_newlines)
    _apply("replace_quotes", _replace_smart_quotes)
    if config.get("remove_timestamps", True):
        _apply("remove_timestamps", _remove_timestamps)
        _apply("collapse_speaker_labels", _collapse_speaker_labels)
    _apply("collapse_whitespace", _collapse_whitespace)
    _apply("normalize_lists", _normalize_lists)
    if config.get("sentence_case_all_caps", True):
        _apply("sentence_case_all_caps", _sentence_case)

    text = text.strip()
    if not text:
        raise NormalizationError(
            "normalized text is empty",
            code="normalization_no_content",
            retryable=False,
        )

    max_output = int(config.get("max_output_chars", 0) or 0)
    if max_output > 0 and len(text) > max_output:
        metadata["truncated"] = True
        metadata["truncated_char_delta"] = len(text) - max_output
        text = text[:max_output]

    emit_segments = bool(config.get("emit_segments", True))
    segment_threshold = int(config.get("segment_threshold_chars", 0) or 0)
    segments: Optional[List[Dict[str, Any]]] = None
    if emit_segments and (segment_threshold <= 0 or len(text) >= segment_threshold):
        segments = _build_segments(text)
    segment_count = len(segments or []) or 1
    metadata["segment_count"] = segment_count

    metadata["output_char_count"] = len(text)
    metadata["applied_rules"] = applied_rules
    metadata["timings"] = timings
    metadata["chunk_count"] = chunk_count_hint or segment_count
    return text, segments, metadata


def _strip_controls_and_bom(text: str) -> Tuple[str, bool]:
    new_text = text.replace("\ufeff", "")
    new_text = _CONTROL_CHARS_RE.sub("", new_text)
    return new_text, new_text != text


def _normalize_newlines(text: str) -> Tuple[str, bool]:
    new_text = text.replace("\r\n", "\n").replace("\r", "\n")
    return new_text, new_text != text


def _replace_smart_quotes(text: str) -> Tuple[str, bool]:
    replacements = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    new_text = text
    for old, new in replacements.items():
        new_text = new_text.replace(old, new)
    return new_text, new_text != text


def _remove_timestamps(text: str) -> Tuple[str, bool]:
    new_text = _TIMESTAMP_RE.sub("", text)
    return new_text, new_text != text


def _collapse_speaker_labels(text: str) -> Tuple[str, bool]:
    new_text = _SPEAKER_RE.sub(lambda match: match.group(1).capitalize() + " ", text)
    return new_text, new_text != text


def _collapse_whitespace(text: str) -> Tuple[str, bool]:
    new_text = re.sub(r"[ \t]{2,}", " ", text)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    return new_text, new_text != text


def _normalize_lists(text: str) -> Tuple[str, bool]:
    new_text = text
    for old, new in _BULLET_REPLACEMENTS.items():
        new_text = new_text.replace(old, new)
    return new_text, new_text != text


def _sentence_case(text: str) -> Tuple[str, bool]:
    stripped = text.strip()
    if not stripped or not stripped.isupper():
        return text, False
    return stripped.capitalize(), True


def _build_segments(text: str) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for index, block in enumerate(text.split("\n\n")):
        chunk = block.strip()
        if not chunk:
            continue
        segment_type = "list" if chunk.lstrip().startswith("-") else "paragraph"
        segments.append(
            {
                "index": len(segments),
                "text": chunk,
                "char_count": len(chunk),
                "type": segment_type,
            }
        )
    return segments


def _record_capture_event(
    gateway: EntryNormalizationStore,
    entry_id: str,
    *,
    event_type: str,
    pipeline_status: str,
    correlation_id: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    data: Dict[str, Any] = {
        "stage": "normalization",
        "pipeline_status": pipeline_status,
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
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "capture_event_failed",
            extra={"entry_id": entry_id, "event_type": event_type},
        )


def _merge_capture_metadata_patch(
    gateway: EntryNormalizationStore,
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


def _resolve_profile(profile_name: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    base = dict(_BASE_PROFILE)
    target_name = profile_name or _DEFAULT_PROFILE
    profile_overrides = _PROFILES.get(target_name)
    if profile_overrides is None and target_name != _DEFAULT_PROFILE:
        logger.warning(
            "normalization_profile_missing_falling_back",
            extra={"profile": target_name},
        )
        profile_overrides = _PROFILES.get(_DEFAULT_PROFILE)
        target_name = _DEFAULT_PROFILE
    if profile_overrides:
        for key, value in profile_overrides.items():
            if value is None:
                continue
            base[key] = value
    return target_name, base


def _elapsed_ms(start_clock: float) -> int:
    return max(0, int((time.perf_counter() - start_clock) * 1000))
