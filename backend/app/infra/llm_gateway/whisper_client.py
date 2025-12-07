"""Faster-Whisper backed transcription client for the INF-04 gateway."""

from __future__ import annotations

import copy
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from backend.app.config import DEFAULT_WHISPER_CONFIG, load_settings

if TYPE_CHECKING:  # pragma: no cover - imported lazily at runtime
    from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: Optional["WhisperModel"] = None
_MODEL_CONFIG: Dict[str, str] = {}
_WHISPER_SETTINGS_CACHE: Optional[Dict[str, Any]] = None


@dataclass
class WhisperSegment:
    """Container for a single transcription segment."""

    start: float
    end: float
    text: str
    tokens: List[int]


@dataclass
class WhisperResult:
    """Structured output from ``transcribe_file``."""

    text: str
    segments: List[WhisperSegment]
    language: Optional[str]
    language_probability: Optional[float]
    duration: Optional[float]
    model_id: str


def is_available() -> bool:
    """Return True when Whisper transcription is enabled via config or env."""

    env_override = _explicit_env_bool("ECHOFORGE_WHISPER_ENABLED")
    if env_override is not None:
        return env_override
    return bool(_whisper_settings().get("enabled"))


def transcribe_file(audio_path: str) -> WhisperResult:
    """Transcribe ``audio_path`` using faster-whisper and return full metadata."""

    if not is_available():
        raise RuntimeError("Whisper transcription is disabled.")

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(audio_path)
    if not path.is_file():
        raise ValueError(f"Transcription source is not a file: {audio_path}")

    model = _get_model()
    segments_iter, info = model.transcribe(str(path), **_decode_options())

    segments: List[WhisperSegment] = []
    collected_text: List[str] = []

    for segment in segments_iter:
        text = segment.text.strip()
        if text:
            collected_text.append(text)
        tokens = list(getattr(segment, "tokens", []) or [])
        segments.append(
            WhisperSegment(
                start=float(segment.start),
                end=float(segment.end),
                text=text,
                tokens=tokens,
            )
        )

    transcript = " ".join(collected_text).strip()
    language = getattr(info, "language", None)
    language_probability = getattr(info, "language_probability", None)
    duration = getattr(info, "duration", None)
    model_id = _MODEL_CONFIG.get("model_id", DEFAULT_WHISPER_CONFIG["model_id"])

    logger.debug(
        "Whisper transcription finished",
        extra={
            "language": language,
            "duration": duration,
            "num_segments": len(segments),
            "model": model_id,
        },
    )

    return WhisperResult(
        text=transcript,
        segments=segments,
        language=language,
        language_probability=language_probability,
        duration=duration,
        model_id=model_id,
    )


def _get_model() -> "WhisperModel":
    global _MODEL_CACHE, _MODEL_CONFIG

    settings = _whisper_settings()
    desired_config = _model_config(settings)

    with _MODEL_LOCK:
        if _MODEL_CACHE is not None and _MODEL_CONFIG == desired_config:
            return _MODEL_CACHE

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - dependency missing in tests
            raise RuntimeError(
                "faster-whisper is not installed; install optional dependency to use Whisper."
            ) from exc

        _MODEL_CACHE = WhisperModel(
            desired_config["model_id"],
            device=desired_config["device"],
            compute_type=desired_config["compute_type"],
        )
        _MODEL_CONFIG = desired_config

        logger.info(
            "Loaded Whisper model",
            extra={
                "model": desired_config["model_id"],
                "device": desired_config["device"],
                "compute_type": desired_config["compute_type"],
            },
        )

        return _MODEL_CACHE


def _model_config(settings: Dict[str, Any]) -> Dict[str, str]:
    return {
        "model_id": str(settings.get("model_id", DEFAULT_WHISPER_CONFIG["model_id"])),
        "device": str(settings.get("device", DEFAULT_WHISPER_CONFIG["device"])),
        "compute_type": str(
            settings.get("compute_type", DEFAULT_WHISPER_CONFIG["compute_type"])
        ),
    }


def _decode_options() -> Dict[str, object]:
    settings = _whisper_settings()
    options: Dict[str, object] = {
        "task": settings.get("task"),
        "language": settings.get("language"),
        "beam_size": settings.get("beam_size"),
        "best_of": settings.get("best_of"),
        "patience": settings.get("patience"),
        "length_penalty": settings.get("length_penalty"),
        "repetition_penalty": settings.get("repetition_penalty"),
        "temperature": settings.get("temperature"),
        "compression_ratio_threshold": settings.get("compression_ratio_threshold"),
        "log_prob_threshold": settings.get("log_prob_threshold"),
        "no_speech_threshold": settings.get("no_speech_threshold"),
        "initial_prompt": settings.get("initial_prompt"),
        "prefix": settings.get("prefix"),
        "condition_on_previous_text": settings.get("condition_on_previous_text"),
        "suppress_blank": settings.get("suppress_blank"),
        "suppress_tokens": settings.get("suppress_tokens"),
        "without_timestamps": settings.get("without_timestamps"),
    }

    if settings.get("vad_enabled"):
        options["vad_filter"] = True
        options["vad_parameters"] = {
            "threshold": settings.get("vad_threshold"),
            "min_speech_duration_ms": settings.get("vad_min_speech"),
            "max_silence_duration_ms": settings.get("vad_max_silence"),
        }

    return {key: value for key, value in options.items() if value is not None}


def _whisper_settings() -> Dict[str, Any]:
    global _WHISPER_SETTINGS_CACHE
    if _WHISPER_SETTINGS_CACHE is None:
        try:
            settings = load_settings()
            llm_cfg = settings.llm or {}
            configured = llm_cfg.get("whisper") or {}
        except Exception:  # pragma: no cover - defensive for config errors
            configured = {}

        merged = copy.deepcopy(DEFAULT_WHISPER_CONFIG)
        for key, value in configured.items():
            if value is None:
                continue
            if isinstance(value, list):
                merged[key] = list(value)
            else:
                merged[key] = value

        _WHISPER_SETTINGS_CACHE = merged

    return _WHISPER_SETTINGS_CACHE


def _explicit_env_bool(var_name: str) -> Optional[bool]:
    value = os.getenv(var_name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized in {"1", "true", "yes", "on"}
