"""INF-01 aligned configuration loader with capture profile support."""

from __future__ import annotations

import copy
import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:  # PyYAML is declared as a dependency but we fall back gracefully if missing.
    import yaml
except ImportError:  # pragma: no cover - exercised only when dependency missing.
    yaml = None  # type: ignore[assignment]

DEFAULT_ENVIRONMENT = "dev"
DEFAULT_RUNTIME_SHAPE = "ShapeA_LocalDev"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://postgres:LuckySebeka@localhost:5432/echo_forge"
)
DEFAULT_MANUAL_HASHING = "sha256:text+channel"
DEFAULT_CAPTURE_WATCH_ROOTS: Sequence[dict[str, Any]] = (
    {
        "id": "default-audio",
        "root_path": "watch_roots/audio",
        "source_channel": "watch_audio",
        "runtime_shapes": ["ShapeA_LocalDev", "ShapeB_DesktopElectron"],
        "file_types": ["audio/mpeg", "audio/wav"],
        "ensure_layout": True,
    },
    {
        "id": "default-documents",
        "root_path": "watch_roots/documents",
        "source_channel": "watch_documents",
        "runtime_shapes": ["ShapeA_LocalDev", "ShapeB_DesktopElectron"],
        "file_types": ["application/pdf", "text/plain"],
        "ensure_layout": True,
    },
)
DEFAULT_CAPTURE_JOB_QUEUE_PROFILE: dict[str, Any] = {
    "backend": "local",
    "queue_name": "capture-dev",
    "enqueue_endpoint": "http://localhost:9001/jobs",
    "default_retry_attempts": 3,
    "default_retry_delay_seconds": 30,
}
DEFAULT_WHISPER_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "model_id": "medium.en",
    "device": "cpu",
    "compute_type": "int8",
    "task": "transcribe",
    "language": None,
    "transcript_output_root": "watch_roots/transcripts",
    "transcript_public_base_url": None,
    "beam_size": 5,
    "best_of": 5,
    "patience": None,
    "length_penalty": 1.0,
    "repetition_penalty": 1.0,
    "temperature": 0.0,
    "temperature_increment_on_fallback": 0.2,
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": None,
    "no_speech_threshold": 0.6,
    "initial_prompt": None,
    "prefix": None,
    "condition_on_previous_text": True,
    "suppress_blank": True,
    "suppress_tokens": [],
    "without_timestamps": False,
    "vad_enabled": False,
    "vad_threshold": 0.5,
    "vad_min_speech": 250,
    "vad_max_silence": 2000,
}

DEFAULT_PROFILE_DICT: dict[str, Any] = {
    "environment": DEFAULT_ENVIRONMENT,
    "runtime_shape": DEFAULT_RUNTIME_SHAPE,
    "database": {"url": DEFAULT_DATABASE_URL},
    "capture": {
        "watch_roots": list(DEFAULT_CAPTURE_WATCH_ROOTS),
        "manual_text": {"hashing": DEFAULT_MANUAL_HASHING},
        "job_queue_profile": DEFAULT_CAPTURE_JOB_QUEUE_PROFILE,
    },
    "llm": {"whisper": copy.deepcopy(DEFAULT_WHISPER_CONFIG)},
}
CONFIG_PROFILE_ENV = "ECHOFORGE_CONFIG_PROFILE"
CONFIG_DIR_ENV = "ECHOFORGE_CONFIG_DIR"
DEFAULT_PROFILE = "dev"
DEFAULT_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "config" / "profiles"
CONFIG_EXTENSIONS = (".yaml", ".yml")


@dataclass
class WatchRootConfig:
    id: str
    root_path: str
    source_channel: str
    runtime_shapes: List[str] = field(default_factory=list)
    file_types: List[str] = field(default_factory=list)
    ensure_layout: bool = True


@dataclass
class ManualTextConfig:
    hashing: str = DEFAULT_MANUAL_HASHING


@dataclass
class CaptureJobQueueProfile:
    backend: str
    queue_name: str
    enqueue_endpoint: str
    default_retry_attempts: int = 3
    default_retry_delay_seconds: int = 30


@dataclass
class CaptureConfig:
    watch_roots: List[WatchRootConfig] = field(default_factory=list)
    manual_text: ManualTextConfig = field(default_factory=ManualTextConfig)
    job_queue_profile: CaptureJobQueueProfile = field(
        default_factory=lambda: CaptureJobQueueProfile(
            **DEFAULT_CAPTURE_JOB_QUEUE_PROFILE
        )
    )


@dataclass
class Settings:
    environment: str = DEFAULT_ENVIRONMENT
    runtime_shape: str = DEFAULT_RUNTIME_SHAPE
    database_url: str = DEFAULT_DATABASE_URL
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    jobqueue: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)
    echo: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def watch_roots(self) -> List[str]:
        """Return configured watch root paths for backward compatibility."""

        return [root.root_path for root in self.capture.watch_roots]


def load_settings(
    profile: str | None = None, config_dir: str | Path | None = None
) -> Settings:
    """Load INF-01 settings from the requested profile or fall back to defaults."""

    profile_name = profile or os.getenv(CONFIG_PROFILE_ENV, DEFAULT_PROFILE)
    config_root = Path(
        config_dir or os.getenv(CONFIG_DIR_ENV, DEFAULT_CONFIG_ROOT)
    ).expanduser()
    config_data = _load_profile_dict(profile_name, config_root)
    if not config_data:
        config_data = copy.deepcopy(DEFAULT_PROFILE_DICT)

    environment = config_data.get("environment", DEFAULT_ENVIRONMENT)
    runtime_shape = config_data.get("runtime_shape", DEFAULT_RUNTIME_SHAPE)

    database_cfg = config_data.get("database", {})
    database_url = os.getenv(
        "DATABASE_URL", database_cfg.get("url", DEFAULT_DATABASE_URL)
    )

    capture_cfg = config_data.get("capture", {})
    capture_config = _build_capture_config(capture_cfg)

    llm_cfg = copy.deepcopy(config_data.get("llm", {}))
    whisper_cfg = _build_whisper_config(llm_cfg.get("whisper"))
    llm_cfg["whisper"] = whisper_cfg

    settings = Settings(
        environment=environment,
        runtime_shape=runtime_shape,
        database_url=database_url,
        capture=capture_config,
        jobqueue=config_data.get("jobqueue", {}),
        llm=llm_cfg,
        logging=config_data.get("logging", {}),
        echo=config_data.get("echo", {}),
        raw=config_data,
    )
    return settings


def _load_profile_dict(profile_name: str, config_root: Path) -> dict[str, Any]:
    """Load the YAML profile if available, otherwise return an empty dict."""

    if not config_root.exists():
        return {}

    for extension in CONFIG_EXTENSIONS:
        candidate = config_root / f"{profile_name}{extension}"
        if not candidate.exists():
            continue
        if yaml is None:
            warnings.warn(
                "PyYAML is not installed; falling back to built-in defaults for settings.",
                RuntimeWarning,
            )
            return {}
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise RuntimeError(
                f"Failed to parse config profile {candidate}: {exc}"
            ) from exc
        if not isinstance(loaded, dict):
            raise RuntimeError(
                f"Config profile {candidate} must be a mapping at the root"
            )
        return loaded

    return {}


def _build_capture_config(capture_cfg: dict[str, Any] | None) -> CaptureConfig:
    capture_cfg = capture_cfg or {}
    watch_roots_cfg = capture_cfg.get("watch_roots") or list(
        DEFAULT_CAPTURE_WATCH_ROOTS
    )
    watch_roots: List[WatchRootConfig] = []
    for entry in watch_roots_cfg:
        root_path = entry.get("root_path")
        if not root_path:
            continue
        watch_roots.append(
            WatchRootConfig(
                id=str(entry.get("id", entry.get("source_channel", root_path))),
                root_path=str(root_path),
                source_channel=str(entry.get("source_channel", "watch_generic")),
                runtime_shapes=list(entry.get("runtime_shapes", [])),
                file_types=list(entry.get("file_types", [])),
                ensure_layout=bool(entry.get("ensure_layout", True)),
            )
        )
    if not watch_roots:
        watch_roots = [
            WatchRootConfig(
                id=item["id"],
                root_path=item["root_path"],
                source_channel=item["source_channel"],
                runtime_shapes=list(item["runtime_shapes"]),
                file_types=list(item["file_types"]),
                ensure_layout=bool(item["ensure_layout"]),
            )
            for item in DEFAULT_CAPTURE_WATCH_ROOTS
        ]

    manual_cfg = capture_cfg.get("manual_text") or {}
    manual_text = ManualTextConfig(
        hashing=str(manual_cfg.get("hashing", DEFAULT_MANUAL_HASHING))
    )

    job_queue_profile = _build_job_queue_profile(capture_cfg.get("job_queue_profile"))

    return CaptureConfig(
        watch_roots=watch_roots,
        manual_text=manual_text,
        job_queue_profile=job_queue_profile,
    )


def _build_job_queue_profile(
    profile_cfg: dict[str, Any] | None,
) -> CaptureJobQueueProfile:
    profile_cfg = profile_cfg or DEFAULT_CAPTURE_JOB_QUEUE_PROFILE
    return CaptureJobQueueProfile(
        backend=str(
            profile_cfg.get("backend", DEFAULT_CAPTURE_JOB_QUEUE_PROFILE["backend"])
        ),
        queue_name=str(
            profile_cfg.get(
                "queue_name", DEFAULT_CAPTURE_JOB_QUEUE_PROFILE["queue_name"]
            )
        ),
        enqueue_endpoint=str(
            profile_cfg.get(
                "enqueue_endpoint",
                DEFAULT_CAPTURE_JOB_QUEUE_PROFILE["enqueue_endpoint"],
            )
        ),
        default_retry_attempts=int(
            profile_cfg.get(
                "default_retry_attempts",
                DEFAULT_CAPTURE_JOB_QUEUE_PROFILE["default_retry_attempts"],
            )
        ),
        default_retry_delay_seconds=int(
            profile_cfg.get(
                "default_retry_delay_seconds",
                DEFAULT_CAPTURE_JOB_QUEUE_PROFILE["default_retry_delay_seconds"],
            )
        ),
    )


def _build_whisper_config(
    whisper_cfg: dict[str, Any] | None,
) -> Dict[str, Any]:
    config = copy.deepcopy(DEFAULT_WHISPER_CONFIG)
    if whisper_cfg:
        for key, value in whisper_cfg.items():
            if value is None:
                continue
            config[key] = value

    overrides: Dict[str, Any] = {
        "enabled": _env_bool("ECHOFORGE_WHISPER_ENABLED"),
        "model_id": _env_str("ECHOFORGE_WHISPER_MODEL_ID"),
        "device": _env_str("ECHOFORGE_WHISPER_DEVICE"),
        "compute_type": _env_str("ECHOFORGE_WHISPER_COMPUTE_TYPE"),
        "task": _env_str("ECHOFORGE_WHISPER_TASK"),
        "language": _env_str("ECHOFORGE_WHISPER_LANGUAGE"),
        "beam_size": _env_int("ECHOFORGE_WHISPER_BEAM_SIZE"),
        "best_of": _env_int("ECHOFORGE_WHISPER_BEST_OF"),
        "patience": _env_float("ECHOFORGE_WHISPER_PATIENCE"),
        "length_penalty": _env_float("ECHOFORGE_WHISPER_LENGTH_PENALTY"),
        "repetition_penalty": _env_float("ECHOFORGE_WHISPER_REPETITION_PENALTY"),
        "temperature": _env_float("ECHOFORGE_WHISPER_TEMPERATURE"),
        "temperature_increment_on_fallback": _env_float(
            "ECHOFORGE_WHISPER_TEMPERATURE_INCREMENT_ON_FALLBACK"
        ),
        "compression_ratio_threshold": _env_float(
            "ECHOFORGE_WHISPER_COMPRESSION_RATIO_THRESHOLD"
        ),
        "log_prob_threshold": _env_float("ECHOFORGE_WHISPER_LOGPROB_THRESHOLD"),
        "no_speech_threshold": _env_float("ECHOFORGE_WHISPER_NO_SPEECH_THRESHOLD"),
        "initial_prompt": _env_str("ECHOFORGE_WHISPER_INITIAL_PROMPT"),
        "prefix": _env_str("ECHOFORGE_WHISPER_PREFIX"),
        "condition_on_previous_text": _env_bool(
            "ECHOFORGE_WHISPER_CONDITION_ON_PREVIOUS_TEXT"
        ),
        "suppress_blank": _env_bool("ECHOFORGE_WHISPER_SUPPRESS_BLANK"),
        "suppress_tokens": _env_csv_ints("ECHOFORGE_WHISPER_SUPPRESS_TOKENS"),
        "without_timestamps": _env_bool("ECHOFORGE_WHISPER_WITHOUT_TIMESTAMPS"),
        "vad_enabled": _env_bool("ECHOFORGE_WHISPER_VAD_ENABLED"),
        "vad_threshold": _env_float("ECHOFORGE_WHISPER_VAD_THRESHOLD"),
        "vad_min_speech": _env_int("ECHOFORGE_WHISPER_VAD_MIN_SPEECH"),
        "vad_max_silence": _env_int("ECHOFORGE_WHISPER_VAD_MAX_SILENCE"),
    }
    for key, value in overrides.items():
        if value is None:
            continue
        config[key] = value
    return config


def _env_str(var_name: str) -> Optional[str]:
    value = os.getenv(var_name)
    if value is None or value == "":
        return None
    return value


def _env_int(var_name: str) -> Optional[int]:
    value = os.getenv(var_name)
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_float(var_name: str) -> Optional[float]:
    value = os.getenv(var_name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _env_bool(var_name: str) -> Optional[bool]:
    value = os.getenv(var_name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "":
        return None
    return normalized in {"1", "true", "yes", "on"}


def _env_csv_ints(var_name: str) -> Optional[List[int]]:
    value = os.getenv(var_name)
    if value is None or not value.strip():
        return None
    tokens: List[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            tokens.append(int(chunk))
        except ValueError:
            continue
    return tokens
