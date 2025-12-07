"""INF-04 LLM gateway entry points."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from . import whisper_client

logger = logging.getLogger(__name__)


def generate_semantic_response(prompt: str) -> str:
    return "LLM output pending"


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
