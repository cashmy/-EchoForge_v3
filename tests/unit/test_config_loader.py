"""Tests for INF-01 config loader behavior."""

# Coverage: INF-01

from __future__ import annotations

import pytest

from backend.app.config import load_settings

pytestmark = [pytest.mark.inf01]


def test_load_settings_falls_back_to_defaults(monkeypatch, tmp_path):
    """Missing profiles should default to the built-in dev configuration."""

    monkeypatch.setenv("ECHOFORGE_CONFIG_PROFILE", "missing")
    monkeypatch.setenv("ECHOFORGE_CONFIG_DIR", str(tmp_path))
    settings = load_settings()

    assert settings.environment == "dev"
    assert settings.runtime_shape == "ShapeA_LocalDev"
    assert settings.database_url.endswith("echo_forge")
    assert settings.watch_roots == ["watch_roots/audio", "watch_roots/documents"]


def test_load_settings_reads_yaml_profile(monkeypatch, tmp_path):
    """Config loader should parse YAML profiles and expose capture settings."""

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_path = profiles_dir / "dev.yaml"
    profile_path.write_text(
        """
environment: staging
runtime_shape: ShapeB_DesktopElectron

database:
  url: "postgresql+psycopg://postgres:pw@db:5432/custom"

capture:
  watch_roots:
    - id: custom
      root_path: "/tmp/watch"
      source_channel: custom_channel
      runtime_shapes: [ShapeB_DesktopElectron]
      ensure_layout: false
  manual_text:
    hashing: sha256:text
  job_queue_profile:
    backend: rq
    queue_name: capture-custom
    enqueue_endpoint: "http://localhost:9999/jobs"
    default_retry_attempts: 5
    default_retry_delay_seconds: 45
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ECHOFORGE_CONFIG_PROFILE", "dev")
    monkeypatch.setenv("ECHOFORGE_CONFIG_DIR", str(profiles_dir))

    settings = load_settings()

    assert settings.environment == "staging"
    assert settings.runtime_shape == "ShapeB_DesktopElectron"
    assert settings.database_url.endswith("custom")
    assert settings.watch_roots == ["/tmp/watch"]
    assert settings.capture.manual_text.hashing == "sha256:text"
    assert settings.capture.job_queue_profile.queue_name == "capture-custom"
    assert settings.capture.job_queue_profile.default_retry_attempts == 5
    assert settings.capture.job_queue_profile.default_retry_delay_seconds == 45
