"""EF-05 semantic worker implementation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from backend.app.config import load_settings
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway
from backend.app.infra import llm_gateway
from backend.app.infra.llm_gateway import PromptSpec, SemanticGatewayError
from backend.app.infra.logging import get_logger

logger = get_logger(__name__)

_SETTINGS = load_settings()
_SUMMARY_CONFIG: Dict[str, Any] = dict(_SETTINGS.echo.get("summary") or {})
_SEMANTIC_PROFILE = "echo_summary_v1"
_DEFAULT_MODE = "auto"


class EntrySemanticStore(Protocol):
    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str) -> Any: ...

    def save_summary(
        self,
        entry_id: str,
        *,
        summary: str,
        display_title: Optional[str],
        model_used: Optional[str],
        semantic_tags: Optional[List[str]],
    ) -> Any: ...

    def save_classification(
        self,
        entry_id: str,
        *,
        type_label: str,
        domain_label: str,
        model_used: Optional[str],
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


class SemanticLlmClient(Protocol):  # pragma: no cover - interface definition
    def generate_semantic_response(
        self,
        *,
        profile: str,
        prompt: PromptSpec,
        model_hint: str = "default",
        user_model_override: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Any: ...


class SemanticWorkerError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


_ENTRY_STORE: Optional[EntrySemanticStore] = None


def _get_default_entry_store() -> EntrySemanticStore:
    global _ENTRY_STORE
    if _ENTRY_STORE is None:
        _ENTRY_STORE = build_entry_store_gateway(fallback_to_memory=True)
    return _ENTRY_STORE


def handle(
    payload: dict,
    *,
    entry_gateway: Optional[EntrySemanticStore] = None,
    llm_client: Optional[SemanticLlmClient] = None,
) -> None:
    gateway = entry_gateway or _get_default_entry_store()
    llm_adapter = llm_client or llm_gateway

    entry_id = payload.get("entry_id")
    if not entry_id:
        raise ValueError("semantic payload missing entry_id")

    user_hint = payload.get("user_hint")
    requested_mode = (payload.get("mode") or _DEFAULT_MODE).lower()
    model_hint = payload.get("model_hint", "default")
    model_override = payload.get("model_override")
    profile = payload.get("profile") or _SEMANTIC_PROFILE
    correlation_id = payload.get("correlation_id")

    gateway.update_pipeline_status(entry_id, pipeline_status="semantic_in_progress")
    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_started",
        pipeline_status="semantic_in_progress",
        correlation_id=correlation_id,
        extra={"profile": profile, "mode": requested_mode},
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {"ingest_state": "processing_semantic"},
    )

    entry = gateway.get_entry(entry_id)
    normalized_text = getattr(entry, "normalized_text", None)
    if not normalized_text:
        error = SemanticWorkerError(
            "normalized text is missing",
            code="semantic_missing_normalized_text",
            retryable=False,
        )
        _handle_failure(
            gateway,
            entry_id,
            error=error,
            correlation_id=correlation_id,
        )
        raise error

    resolved_mode = _resolve_mode(requested_mode, len(normalized_text))
    prompt_text = _build_prompt_text(entry, normalized_text, resolved_mode)
    system_prompt = (
        "You are summarizing a single EchoForge Entry. Produce: "
        "1) A concise summary (2-5 sentences). "
        "2) A single-line display_title (<120 chars). "
        "Do not create plans or multi-entry references."
    )
    prompt = PromptSpec(system=system_prompt, user=prompt_text, user_hint=user_hint)

    start_clock = time.perf_counter()
    attempts = 0
    max_attempts = max(1, int(_SUMMARY_CONFIG.get("max_retry_attempts", 2) or 2))
    backoff_ms = max(0, int(_SUMMARY_CONFIG.get("retry_backoff_ms", 250) or 250))
    while True:
        attempts += 1
        try:
            response = llm_adapter.generate_semantic_response(
                profile=profile,
                prompt=prompt,
                model_hint=model_hint,
                user_model_override=model_override,
                correlation_id=correlation_id,
            )
            break
        except SemanticGatewayError as exc:
            should_retry = exc.retryable and attempts < max_attempts
            if not should_retry:
                error = SemanticWorkerError(
                    str(exc), code=exc.code, retryable=exc.retryable
                )
                _handle_failure(
                    gateway,
                    entry_id,
                    error=error,
                    correlation_id=correlation_id,
                )
                raise error
            delay_seconds = (backoff_ms * (2 ** (attempts - 1))) / 1000.0
            logger.warning(
                "semantic_llm_retry_scheduled",
                extra={
                    "entry_id": entry_id,
                    "attempt": attempts,
                    "max_attempts": max_attempts,
                    "delay_seconds": delay_seconds,
                    "error_code": exc.code,
                },
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            continue

    processing_ms = _elapsed_ms(start_clock)
    summary_text = _response_value(response, "summary") or prompt_text[:400]
    display_title = _response_value(response, "display_title") or _fallback_title(
        prompt_text
    )
    tags = _response_tags(response)
    model_used = _response_value(response, "model_used")
    type_label = _coerce_str(_response_value(response, "type_label"))
    domain_label = _coerce_str(_response_value(response, "domain_label"))

    gateway.save_summary(
        entry_id,
        summary=summary_text,
        display_title=display_title,
        model_used=model_used,
        semantic_tags=tags or None,
    )
    if type_label and domain_label:
        try:
            gateway.save_classification(
                entry_id,
                type_label=type_label,
                domain_label=domain_label,
                model_used=model_used,
            )
        except AttributeError:
            logger.debug(
                "classification_save_not_supported",
                extra={"entry_id": entry_id},
            )
    gateway.update_pipeline_status(entry_id, pipeline_status="semantic_complete")

    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_completed",
        pipeline_status="semantic_complete",
        correlation_id=correlation_id,
        extra={
            "profile": profile,
            "mode": resolved_mode,
            "model": model_used,
            "processing_ms": processing_ms,
            "attempts": attempts,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "ingest_state": "processed",
            "semantics": {
                "profile": profile,
                "mode": resolved_mode,
                "model": model_used,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "input_char_count": len(prompt_text),
                "processing_ms": processing_ms,
                "tags": tags,
                "type_label": type_label,
                "domain_label": domain_label,
                "attempts": attempts,
            },
        },
    )


def _handle_failure(
    gateway: EntrySemanticStore,
    entry_id: str,
    *,
    error: SemanticWorkerError,
    correlation_id: Optional[str],
) -> None:
    gateway.update_pipeline_status(entry_id, pipeline_status="semantic_failed")
    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_failed",
        pipeline_status="semantic_failed",
        correlation_id=correlation_id,
        extra={"error_code": error.code, "retryable": error.retryable},
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "ingest_state": "failed",
            "last_error": {
                "stage": "semantics",
                "code": error.code,
                "retryable": error.retryable,
            },
        },
    )


def _record_capture_event(
    gateway: EntrySemanticStore,
    entry_id: str,
    *,
    event_type: str,
    pipeline_status: str,
    correlation_id: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    data: Dict[str, Any] = {"stage": "semantics", "pipeline_status": pipeline_status}
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
    gateway: EntrySemanticStore,
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


def _resolve_mode(mode: str, text_length: int) -> str:
    normalized_mode = (mode or _DEFAULT_MODE).lower()
    if normalized_mode not in {"auto", "preview", "deep"}:
        raise ValueError(f"unsupported semantic mode '{mode}'")
    if normalized_mode == "auto":
        threshold = int(_SUMMARY_CONFIG.get("max_deep_chars", 6000) or 6000)
        if threshold <= 0 or text_length <= threshold:
            return "deep"
        return "preview"
    return normalized_mode


def _build_prompt_text(entry: Any, normalized_text: str, mode: str) -> str:
    if mode == "preview":
        max_preview = int(_SUMMARY_CONFIG.get("max_preview_chars", 400) or 400)
        if max_preview > 0:
            return normalized_text[:max_preview]
        preview = getattr(entry, "verbatim_preview", None) or normalized_text
        return preview[:400]

    max_deep = int(_SUMMARY_CONFIG.get("max_deep_chars", 6000) or 6000)
    if max_deep > 0:
        return normalized_text[:max_deep]
    return normalized_text


def _response_value(response: Any, key: str) -> Optional[Any]:
    if hasattr(response, key):
        return getattr(response, key)
    if isinstance(response, dict):
        return response.get(key)
    return None


def _response_tags(response: Any) -> List[str]:
    value = _response_value(response, "tags")
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        tags: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if not cleaned:
                continue
            if cleaned in tags:
                continue
            tags.append(cleaned)
        return tags
    return []


def _coerce_str(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _fallback_title(text: str) -> str:
    snippet = (text or "").strip()
    if not snippet:
        return "Semantic Summary"
    first_line = snippet.splitlines()[0]
    return first_line[:120]


def _elapsed_ms(start_clock: float) -> int:
    return max(0, int((time.perf_counter() - start_clock) * 1000))
