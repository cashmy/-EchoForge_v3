"""Unit tests for the faster-whisper client plumbing."""

# Coverage: INF-04

from __future__ import annotations

import sys
import types

import pytest

from backend.app.infra.llm_gateway import whisper_client

pytestmark = [pytest.mark.inf04]


@pytest.fixture(autouse=True)
def reset_whisper_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure each test exercises a clean cache state."""

    monkeypatch.setattr(whisper_client, "_WHISPER_SETTINGS_CACHE", None)
    monkeypatch.setattr(whisper_client, "_MODEL_CACHE", None)
    monkeypatch.setattr(whisper_client, "_MODEL_CONFIG", {})


def test_is_available_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variable must win over config when explicitly set."""

    monkeypatch.setenv("ECHOFORGE_WHISPER_ENABLED", "0")
    monkeypatch.setattr(whisper_client, "_WHISPER_SETTINGS_CACHE", {"enabled": True})

    assert whisper_client.is_available() is False


def test_is_available_falls_back_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without env override, cached config decides availability."""

    monkeypatch.delenv("ECHOFORGE_WHISPER_ENABLED", raising=False)
    monkeypatch.setattr(whisper_client, "_WHISPER_SETTINGS_CACHE", {"enabled": True})

    assert whisper_client.is_available() is True


def test_decode_options_include_vad_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """VAD configuration is passed to faster-whisper when enabled."""

    settings = {
        "enabled": True,
        "task": "transcribe",
        "beam_size": 5,
        "vad_enabled": True,
        "vad_threshold": 0.55,
        "vad_min_speech": 150,
        "vad_max_silence": 900,
        "language": None,  # Should be filtered from decode options
    }
    monkeypatch.setattr(whisper_client, "_WHISPER_SETTINGS_CACHE", settings)

    options = whisper_client._decode_options()

    assert options["vad_filter"] is True
    assert options["vad_parameters"] == {
        "threshold": 0.55,
        "min_speech_duration_ms": 150,
        "max_silence_duration_ms": 900,
    }
    assert "language" not in options  # None should drop from payload


def test_get_model_reuses_cache_when_config_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whisper model is instantiated only once for a stable config."""

    class DummyModel:
        def __init__(self, model_id: str, device: str, compute_type: str) -> None:
            self.model_id = model_id
            self.device = device
            self.compute_type = compute_type

    monkeypatch.setitem(
        sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=DummyModel)
    )
    monkeypatch.setattr(
        whisper_client,
        "_WHISPER_SETTINGS_CACHE",
        {
            "enabled": True,
            "model_id": "tiny",
            "device": "cpu",
            "compute_type": "int8",
        },
    )

    first_instance = whisper_client._get_model()
    second_instance = whisper_client._get_model()

    assert first_instance is second_instance
    assert first_instance.model_id == "tiny"
    assert whisper_client._MODEL_CONFIG["model_id"] == "tiny"
