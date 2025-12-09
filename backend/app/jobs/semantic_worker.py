"""EF-05 semantic worker implementation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from backend.app.config import load_settings
from backend.app.domain.ef06_entrystore.gateway import build_entry_store_gateway
from backend.app.domain.ef06_entrystore.pipeline_states import PIPELINE_STATUS
from backend.app.infra import llm_gateway
from backend.app.infra.llm_gateway import PromptSpec, SemanticGatewayError
from backend.app.infra.logging import get_logger

logger = get_logger(__name__)

_SETTINGS = load_settings()
_SUMMARY_CONFIG: Dict[str, Any] = dict(_SETTINGS.echo.get("summary") or {})
_SUMMARY_PROFILE = "echo_summary_v1"
_CLASSIFY_PROFILE = "echo_classify_v1"
_DEFAULT_OPERATION = "summarize_v1"
_OPERATION_PROFILES = {
    "summarize_v1": _SUMMARY_PROFILE,
    "classify_v1": _CLASSIFY_PROFILE,
}
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

    operation = _resolve_operation(payload.get("operation"))
    requested_mode = (payload.get("mode") or _DEFAULT_MODE).lower()
    model_hint = payload.get("model_hint", "default")
    model_override = payload.get("model_override")
    profile = payload.get("profile") or _OPERATION_PROFILES[operation]
    correlation_id = payload.get("correlation_id")
    user_hint = _compose_user_hint(
        base_hint=payload.get("user_hint"),
        classification_hint=payload.get("classification_hint"),
        operation=operation,
    )

    entry = gateway.get_entry(entry_id)
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.SEMANTIC_IN_PROGRESS,
    )
    pipeline_status = PIPELINE_STATUS.SEMANTIC_IN_PROGRESS
    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_started",
        pipeline_status=pipeline_status,
        correlation_id=correlation_id,
        extra={
            "profile": profile,
            "mode": requested_mode,
            "operation": operation,
            "model_hint": model_hint,
        },
    )
    logger.info(
        "semantic_job_started",
        extra={
            "entry_id": entry_id,
            "operation": operation,
            "mode": requested_mode,
            "profile": profile,
            "model_hint": model_hint,
            "correlation_id": correlation_id,
            "stage": "semantics",
            "pipeline_status": PIPELINE_STATUS.SEMANTIC_IN_PROGRESS,
        },
    )
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
            operation=operation,
            error=error,
            correlation_id=correlation_id,
        )
        raise error

    resolved_mode = _resolve_mode(requested_mode, len(normalized_text))
    prompt_text = _build_prompt_text(entry, normalized_text, resolved_mode)
    system_prompt = _build_system_prompt(operation)
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
                    operation=operation,
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
                    "stage": "semantics",
                    "pipeline_status": PIPELINE_STATUS.SEMANTIC_IN_PROGRESS,
                },
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            continue

    existing_summary = getattr(entry, "summary", None)
    existing_title = getattr(entry, "display_title", None)
    existing_tags = list(getattr(entry, "semantic_tags") or [])

    processing_ms = _elapsed_ms(start_clock)
    summary_value = _response_value(response, "summary")
    display_value = _response_value(response, "display_title")
    summary_text = _select_summary_text(
        operation=operation,
        summary_value=summary_value,
        prompt_text=prompt_text,
        existing_summary=existing_summary,
    )
    display_title = _select_display_title(
        operation=operation,
        title_value=display_value,
        prompt_text=prompt_text,
        existing_title=existing_title,
    )
    response_tags = _response_tags(response)
    confidence = _response_confidence(response)
    if response_tags:
        final_tags: Optional[List[str]] = response_tags
    elif existing_tags:
        final_tags = list(existing_tags)
    else:
        final_tags = None
    model_used = _response_value(response, "model_used")
    type_label = _coerce_str(_response_value(response, "type_label"))
    domain_label = _coerce_str(_response_value(response, "domain_label"))

    summary_model_value = getattr(entry, "summary_model", None)
    if operation == "summarize_v1" and model_used:
        summary_model_value = model_used

    gateway.save_summary(
        entry_id,
        summary=summary_text,
        display_title=display_title,
        model_used=summary_model_value,
        semantic_tags=final_tags,
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
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.SEMANTIC_COMPLETE,
    )
    pipeline_status = PIPELINE_STATUS.SEMANTIC_COMPLETE
    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_completed",
        pipeline_status=pipeline_status,
        correlation_id=correlation_id,
        extra={
            "profile": profile,
            "mode": resolved_mode,
            "model": model_used,
            "operation": operation,
            "processing_ms": processing_ms,
            "attempts": attempts,
            "tags": final_tags,
            "type_label": type_label,
            "domain_label": domain_label,
            "summary_confidence": confidence.get("summary"),
            "classification_confidence": confidence.get("classification"),
        },
    )
    logger.info(
        "semantic_job_completed",
        extra={
            "entry_id": entry_id,
            "operation": operation,
            "mode": resolved_mode,
            "profile": profile,
            "model": model_used,
            "processing_ms": processing_ms,
            "attempts": attempts,
            "tags": final_tags,
            "type_label": type_label,
            "domain_label": domain_label,
            "summary_confidence": confidence.get("summary"),
            "classification_confidence": confidence.get("classification"),
            "correlation_id": correlation_id,
            "stage": "semantics",
            "pipeline_status": PIPELINE_STATUS.SEMANTIC_COMPLETE,
        },
    )
    confidence_payload = _confidence_payload(confidence)

    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "semantics": {
                "profile": profile,
                "mode": resolved_mode,
                "operation": operation,
                "model": model_used,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "input_char_count": len(prompt_text),
                "processing_ms": processing_ms,
                "tags": final_tags or [],
                "type_label": type_label,
                "domain_label": domain_label,
                "attempts": attempts,
                "confidence": confidence_payload,
            },
        },
    )


def _handle_failure(
    gateway: EntrySemanticStore,
    entry_id: str,
    *,
    operation: str,
    error: SemanticWorkerError,
    correlation_id: Optional[str],
) -> None:
    gateway.update_pipeline_status(
        entry_id,
        pipeline_status=PIPELINE_STATUS.SEMANTIC_FAILED,
    )
    _record_capture_event(
        gateway,
        entry_id,
        event_type="semantic_failed",
        pipeline_status=PIPELINE_STATUS.SEMANTIC_FAILED,
        correlation_id=correlation_id,
        extra={
            "error_code": error.code,
            "retryable": error.retryable,
            "operation": operation,
        },
    )
    logger.error(
        "semantic_job_failed",
        extra={
            "entry_id": entry_id,
            "operation": operation,
            "error_code": error.code,
            "retryable": error.retryable,
            "correlation_id": correlation_id,
            "stage": "semantics",
            "pipeline_status": PIPELINE_STATUS.SEMANTIC_FAILED,
        },
    )
    _merge_capture_metadata_patch(
        gateway,
        entry_id,
        {
            "last_error": {
                "stage": "semantics",
                "code": error.code,
                "retryable": error.retryable,
                "operation": operation,
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


def _resolve_operation(value: Optional[str]) -> str:
    operation = (value or _DEFAULT_OPERATION).strip().lower()
    if operation not in _OPERATION_PROFILES:
        raise ValueError(f"unsupported semantic operation '{value}'")
    return operation


def _compose_user_hint(
    *,
    base_hint: Optional[str],
    classification_hint: Optional[str],
    operation: str,
) -> Optional[str]:
    parts: List[str] = []
    if base_hint:
        trimmed = base_hint.strip()
        if trimmed:
            parts.append(trimmed)
    if operation == "classify_v1" and classification_hint:
        trimmed = classification_hint.strip()
        if trimmed:
            parts.append(trimmed)
    merged = "\n\n".join(part for part in parts if part)
    return merged or None


def _build_system_prompt(operation: str) -> str:
    if operation == "classify_v1":
        return (
            "You are classifying a single EchoForge Entry. "
            "Provide concise type_label and domain_label values, "
            "plus optional tags describing key themes. Prefer "
            "existing vocabulary names when possible."
        )
    return (
        "You are summarizing a single EchoForge Entry. Produce: "
        "1) A concise summary (2-5 sentences). "
        "2) A single-line display_title (<120 chars). "
        "Do not create plans or multi-entry references."
    )


def _select_summary_text(
    *,
    operation: str,
    summary_value: Optional[Any],
    prompt_text: str,
    existing_summary: Optional[str],
) -> str:
    if isinstance(summary_value, str) and summary_value.strip():
        return summary_value
    if operation == "summarize_v1":
        return prompt_text[:400]
    return existing_summary or prompt_text[:400]


def _select_display_title(
    *,
    operation: str,
    title_value: Optional[Any],
    prompt_text: str,
    existing_title: Optional[str],
) -> str:
    if isinstance(title_value, str) and title_value.strip():
        return title_value
    if operation == "summarize_v1":
        return _fallback_title(prompt_text)
    return existing_title or _fallback_title(prompt_text)


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
        normalized = _normalize_tag(value)
        return [normalized] if normalized else []
    if isinstance(value, list):
        tags: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = _normalize_tag(item)
            if not normalized:
                continue
            if normalized in tags:
                continue
            tags.append(normalized)
        return tags
    return []


def _coerce_str(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _normalize_tag(tag: str) -> Optional[str]:
    cleaned = tag.strip().lower()
    if not cleaned:
        return None
    if len(cleaned) > 32:
        cleaned = cleaned[:32]
    return cleaned


def _response_confidence(response: Any) -> Dict[str, Optional[float]]:
    value = _response_value(response, "confidence")
    result: Dict[str, Optional[float]] = {
        "summary": None,
        "classification": None,
    }
    if not isinstance(value, dict):
        return result
    result["summary"] = _coerce_confidence(value.get("summary"))
    result["classification"] = _coerce_confidence(value.get("classification"))
    return result


def _coerce_confidence(raw: Optional[Any]) -> Optional[float]:
    if raw is None:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 1:
        return None
    return number


def _confidence_payload(
    confidence: Dict[str, Optional[float]],
) -> Optional[Dict[str, float]]:
    filtered = {k: v for k, v in confidence.items() if v is not None}
    return filtered or None


def _fallback_title(text: str) -> str:
    snippet = (text or "").strip()
    if not snippet:
        return "Semantic Summary"
    first_line = snippet.splitlines()[0]
    return first_line[:120]


def _elapsed_ms(start_clock: float) -> int:
    return max(0, int((time.perf_counter() - start_clock) * 1000))
