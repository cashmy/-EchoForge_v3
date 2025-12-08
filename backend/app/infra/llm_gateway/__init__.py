"""INF-04 LLM gateway entry points."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...config import load_settings
from . import whisper_client

logger = logging.getLogger(__name__)

__all__ = [
    "PromptSpec",
    "SemanticResponse",
    "SemanticGatewayError",
    "generate_semantic_response",
    "TranscriptionGatewayError",
    "transcribe_audio",
]


@dataclass(frozen=True)
class PromptSpec:
    """Structured prompt used for semantic requests."""

    system: str
    user: str
    user_hint: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None


@dataclass(frozen=True)
class LlmResult:
    """Raw result returned by the provider drivers."""

    text: str
    model_used: str
    usage: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class SemanticResponse:
    """Normalized semantic response returned to EF-05."""

    model_used: str
    summary: Optional[str] = None
    display_title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    type_label: Optional[str] = None
    domain_label: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    profile: Optional[str] = None


class SemanticGatewayError(RuntimeError):
    """Raised when semantic LLM operations cannot complete."""

    def __init__(self, message: str, *, code: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


_SETTINGS = load_settings()
_LLM_CONFIG: Dict[str, Any] = dict(_SETTINGS.llm or {})
_LLM_PROFILES: Dict[str, Dict[str, Any]] = {
    key: dict(value or {}) for key, value in (_LLM_CONFIG.get("profiles") or {}).items()
}
_DEFAULT_PROVIDER = _LLM_CONFIG.get("default_provider", "stub")
_DEFAULT_MODEL = _LLM_CONFIG.get("default_model", "stub-model")


def generate_semantic_response(
    *,
    profile: str,
    prompt: PromptSpec,
    model_hint: str = "default",
    user_model_override: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> SemanticResponse:
    """Return semantic response using configured LLM profile.

    Falls back to a deterministic stub response when no provider driver is configured.
    """

    user_text = (prompt.user or "").strip()
    if not user_text:
        raise SemanticGatewayError(
            "semantic prompt text is empty",
            code="semantic_prompt_empty",
            retryable=False,
        )

    profile_cfg = dict(_LLM_PROFILES.get(profile) or {})
    if not profile_cfg:
        raise SemanticGatewayError(
            f"semantic profile '{profile}' is not configured",
            code="semantic_profile_missing",
            retryable=False,
        )

    provider = profile_cfg.get("provider") or _DEFAULT_PROVIDER
    model = user_model_override or profile_cfg.get("model") or _DEFAULT_MODEL

    logger.debug(
        "semantic_llm_request_prepared",
        extra={
            "profile": profile,
            "provider": provider,
            "model": model,
            "model_hint": model_hint,
            "correlation_id": correlation_id,
        },
    )

    llm_result = _execute_semantic_request(
        provider=provider,
        model=model,
        prompt=prompt,
        profile=profile,
        model_hint=model_hint,
    )
    structured = _parse_structured_semantic_result(
        llm_result.text,
        prompt=prompt,
    )
    return SemanticResponse(
        model_used=llm_result.model_used,
        summary=structured["summary"],
        display_title=structured["display_title"],
        tags=structured["tags"],
        type_label=structured["type_label"],
        domain_label=structured["domain_label"],
        usage=llm_result.usage,
        raw_text=llm_result.text,
        profile=profile,
    )


def _execute_semantic_request(
    *,
    provider: str,
    model: str,
    prompt: PromptSpec,
    profile: str,
    model_hint: str,
) -> LlmResult:
    if provider == "stub" or provider == "openai":  # placeholder routing
        return _generate_stub_llm_result(
            prompt=prompt,
            provider=provider,
            model=model,
            profile=profile,
            model_hint=model_hint,
        )

    logger.warning(
        "semantic_llm_provider_unimplemented",
        extra={"provider": provider, "profile": profile},
    )
    return _generate_stub_llm_result(
        prompt=prompt,
        provider=provider,
        model=model,
        profile=profile,
        model_hint=model_hint,
    )


def _generate_stub_llm_result(
    *,
    prompt: PromptSpec,
    provider: str,
    model: str,
    profile: str,
    model_hint: str,
) -> LlmResult:
    provider_label = provider or "stub"
    model_label = model or "semantic"
    model_used = f"{provider_label}:{model_label}" if provider_label else model_label

    normalized_text = _normalize_whitespace(prompt.user)
    summary = _build_stub_summary(normalized_text, hint=prompt.user_hint)
    display_title = _build_stub_title(normalized_text)
    tags = _build_stub_tags(normalized_text)
    classification = _build_stub_classification(normalized_text)
    structured_payload = {
        "summary": summary,
        "display_title": display_title,
        "tags": tags,
        "classification": classification,
    }
    usage = {
        "profile": profile,
        "mode": "stub",
        "chars": len(normalized_text),
        "model_hint": model_hint,
    }
    raw_text = json.dumps(structured_payload, ensure_ascii=False)

    logger.info(
        "semantic_llm_stub_used",
        extra={
            "profile": profile,
            "provider": provider_label,
            "model": model_label,
            "model_hint": model_hint,
        },
    )

    return LlmResult(text=raw_text, model_used=model_used, usage=usage)


def _parse_structured_semantic_result(
    raw_text: str,
    *,
    prompt: PromptSpec,
) -> Dict[str, Any]:
    defaults = _default_semantic_fields(prompt)
    if not raw_text or not raw_text.strip():
        return defaults

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SemanticGatewayError(
            "semantic response is not valid JSON",
            code="semantic_response_invalid_json",
            retryable=False,
        ) from exc

    if not isinstance(payload, dict):
        raise SemanticGatewayError(
            "semantic response payload must be a JSON object",
            code="semantic_response_invalid_payload",
            retryable=False,
        )

    classification = payload.get("classification")
    if not isinstance(classification, dict):
        classification = {}

    summary = _coerce_string(payload.get("summary")) or defaults["summary"]
    display_title = (
        _coerce_string(payload.get("display_title") or payload.get("title"))
        or defaults["display_title"]
    )
    tags = _coerce_tags(payload.get("tags"))
    if not tags:
        tags = _coerce_tags(payload.get("keywords"))
    if not tags:
        tags = defaults["tags"]

    type_label = (
        _coerce_string(classification.get("type_label") or payload.get("type_label"))
        or defaults["type_label"]
    )
    domain_label = (
        _coerce_string(
            classification.get("domain_label") or payload.get("domain_label")
        )
        or defaults["domain_label"]
    )

    return {
        "summary": summary,
        "display_title": display_title,
        "tags": tags,
        "type_label": type_label,
        "domain_label": domain_label,
    }


def _default_semantic_fields(prompt: PromptSpec) -> Dict[str, Any]:
    normalized_text = _normalize_whitespace(prompt.user)
    summary = _build_stub_summary(normalized_text, hint=prompt.user_hint)
    display_title = _build_stub_title(normalized_text)
    tags = _build_stub_tags(normalized_text)
    classification = _build_stub_classification(normalized_text)
    return {
        "summary": summary,
        "display_title": display_title,
        "tags": tags,
        "type_label": classification["type_label"],
        "domain_label": classification["domain_label"],
    }


def _normalize_whitespace(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text or "")
    return collapsed.strip()


def _build_stub_summary(text: str, *, hint: Optional[str]) -> str:
    if not text:
        base = "No semantic content available."
    else:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        base = " ".join(sentences[:3]).strip() or textwrap.shorten(
            text, width=400, placeholder="…"
        )
    if hint:
        hint_text = hint.strip()
        if hint_text:
            base = f"{base} Hint: {hint_text}".strip()
    return textwrap.shorten(base, width=600, placeholder="…")


def _build_stub_title(text: str) -> str:
    if not text:
        return "Untitled Entry"
    for candidate in text.splitlines():
        stripped = candidate.strip()
        if stripped:
            return textwrap.shorten(stripped, width=120, placeholder="…")
    return "Untitled Entry"


def _build_stub_tags(text: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9]+", text or "")
    seen: set[str] = set()
    tags: List[str] = []
    for word in words:
        normalized = word.strip()
        if len(normalized) < 4:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(normalized.title())
        if len(tags) >= 5:
            break
    if not tags:
        return ["EchoForge", "Entry"]
    return tags


def _build_stub_classification(text: str) -> Dict[str, str]:
    lowered = (text or "").lower()
    if "meeting" in lowered or "standup" in lowered:
        return {"type_label": "MeetingNote", "domain_label": "Operations"}
    if "architecture" in lowered or "design" in lowered:
        return {"type_label": "ArchitectureNote", "domain_label": "Engineering"}
    if "journal" in lowered or "reflection" in lowered:
        return {"type_label": "JournalEntry", "domain_label": "Personal"}
    return {"type_label": "Entry", "domain_label": "General"}


def _coerce_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _coerce_tags(value: Any) -> List[str]:
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


class TranscriptionGatewayError(RuntimeError):
    """Raised when Whisper-based transcription cannot complete."""

    def __init__(self, message: str, *, code: str, retryable: bool):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def transcribe_audio(
    source_path: str,
    *,
    language_hint: Optional[str] = None,
    profile: str = "transcribe_v1",
) -> Dict[str, object]:
    """Return real Whisper output when enabled, otherwise fall back to stub."""

    if not whisper_client.is_available():
        logger.debug("Whisper disabled; returning stub transcription")
        return _stub_transcription(
            source_path, language_hint=language_hint, profile=profile
        )

    try:
        result = whisper_client.transcribe_file(source_path)
    except FileNotFoundError as exc:
        raise TranscriptionGatewayError(
            str(exc), code="media_unreadable", retryable=False
        ) from exc
    except PermissionError as exc:
        raise TranscriptionGatewayError(
            str(exc), code="media_unreadable", retryable=False
        ) from exc
    except ValueError as exc:
        raise TranscriptionGatewayError(
            str(exc), code="unsupported_format", retryable=False
        ) from exc
    except TimeoutError as exc:  # pragma: no cover - defensive
        raise TranscriptionGatewayError(
            str(exc), code="llm_timeout", retryable=True
        ) from exc
    except RuntimeError as exc:  # pragma: no cover - defensive
        message = str(exc)
        code = (
            "llm_rate_limited" if "rate limit" in message.lower() else "internal_error"
        )
        raise TranscriptionGatewayError(
            message, code=code, retryable=code != "internal_error"
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive safety net
        raise TranscriptionGatewayError(
            str(exc), code="internal_error", retryable=False
        ) from exc

    language = result.language or language_hint or "und"
    confidence = result.language_probability
    segments = [_segment_to_dict(segment) for segment in result.segments]
    duration_ms = _duration_ms(result)

    return {
        "text": result.text,
        "segments": segments,
        "language": language,
        "confidence": confidence,
        "model": result.model_id,
        "duration_ms": duration_ms,
    }


def _stub_transcription(
    source_path: str, *, language_hint: Optional[str], profile: str
) -> Dict[str, object]:
    path = Path(source_path)
    inferred_text = path.stem.replace("_", " ") or "sample audio"
    return {
        "text": inferred_text,
        "segments": [],
        "language": language_hint or "und",
        "confidence": 0.5,
        "model": f"stub::{profile}",
        "duration_ms": 0,
    }


def _segment_to_dict(segment: whisper_client.WhisperSegment) -> Dict[str, object]:
    return {
        "start": segment.start,
        "end": segment.end,
        "text": segment.text,
        "tokens": segment.tokens,
    }


def _duration_ms(result: whisper_client.WhisperResult) -> int:
    if result.duration is not None:
        return int(result.duration * 1000)
    if result.segments:
        return int(result.segments[-1].end * 1000)
    return 0
