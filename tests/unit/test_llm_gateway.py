"""Unit tests for the INF-04 gateway entry point wrappers."""

# Coverage: EF-02, INF-04

from __future__ import annotations

import pytest

from backend.app.infra import llm_gateway
from backend.app.infra.llm_gateway import (
    PromptSpec,
    SemanticGatewayError,
    whisper_client,
)

pytestmark = [pytest.mark.ef02, pytest.mark.ef05, pytest.mark.inf04]


def test_transcribe_audio_returns_stub_when_disabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When Whisper is disabled the stub data should be returned."""

    source = tmp_path / "meeting_notes.wav"
    source.write_bytes(b"fake audio")

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: False)

    result = llm_gateway.transcribe_audio(
        str(source), language_hint="en", profile="transcribe_v1"
    )

    assert result["model"] == "stub::transcribe_v1"
    assert result["language"] == "en"
    assert "segments" in result


def test_transcribe_audio_formats_real_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Gateway should return the structured payload from whisper_client results."""

    source = tmp_path / "call.wav"
    source.write_bytes(b"fake audio")

    segment = whisper_client.WhisperSegment(
        start=0.0, end=1.5, text="Hello", tokens=[1, 2]
    )
    result = whisper_client.WhisperResult(
        text="Hello world",
        segments=[segment],
        language="en",
        language_probability=0.99,
        duration=1.5,
        model_id="medium.en",
    )

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_gateway.whisper_client, "transcribe_file", lambda _: result)

    response = llm_gateway.transcribe_audio(
        str(source), language_hint="und", profile="transcribe_v1"
    )

    assert response["text"] == "Hello world"
    assert response["language"] == "en"
    assert response["confidence"] == 0.99
    assert response["model"] == "medium.en"
    assert response["duration_ms"] == 1500
    assert response["segments"] == [
        {"start": 0.0, "end": 1.5, "text": "Hello", "tokens": [1, 2]}
    ]


def test_transcribe_audio_translates_file_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """File/permission failures must bubble up as gateway errors."""

    source = tmp_path / "missing.wav"

    def _raise(_: str) -> None:
        raise FileNotFoundError("boom")

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_gateway.whisper_client, "transcribe_file", _raise)

    with pytest.raises(llm_gateway.TranscriptionGatewayError) as exc_info:
        llm_gateway.transcribe_audio(str(source))

    err = exc_info.value
    assert err.code == "media_unreadable"
    assert err.retryable is False


def test_transcribe_audio_translates_timeout_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    source = tmp_path / "clip.wav"
    source.write_bytes(b"fake")

    def _raise(_: str) -> None:
        raise TimeoutError("slow")

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_gateway.whisper_client, "transcribe_file", _raise)

    with pytest.raises(llm_gateway.TranscriptionGatewayError) as exc_info:
        llm_gateway.transcribe_audio(str(source))

    err = exc_info.value
    assert err.code == "llm_timeout"
    assert err.retryable is True


def test_transcribe_audio_translates_rate_limit_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    source = tmp_path / "clip.wav"
    source.write_bytes(b"fake")

    def _raise(_: str) -> None:
        raise RuntimeError("Rate limit exceeded")

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_gateway.whisper_client, "transcribe_file", _raise)

    with pytest.raises(llm_gateway.TranscriptionGatewayError) as exc_info:
        llm_gateway.transcribe_audio(str(source))

    err = exc_info.value
    assert err.code == "llm_rate_limited"
    assert err.retryable is True


def test_transcribe_audio_translates_generic_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    source = tmp_path / "clip.wav"
    source.write_bytes(b"fake")

    def _raise(_: str) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(llm_gateway.whisper_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_gateway.whisper_client, "transcribe_file", _raise)

    with pytest.raises(llm_gateway.TranscriptionGatewayError) as exc_info:
        llm_gateway.transcribe_audio(str(source))

    err = exc_info.value
    assert err.code == "internal_error"
    assert err.retryable is False


def test_generate_semantic_response_returns_stub_summary() -> None:
    prompt = PromptSpec(
        system="test",
        user="EchoForge semantics worker brings summaries online.",
    )

    response = llm_gateway.generate_semantic_response(
        profile="echo_summary_v1", prompt=prompt
    )

    assert "EchoForge" in response.summary
    assert len(response.display_title) <= 120
    assert "gpt-4o-mini" in response.model_used
    assert response.tags and all(isinstance(tag, str) for tag in response.tags)
    assert response.type_label
    assert response.domain_label


def test_generate_semantic_response_rejects_empty_text() -> None:
    prompt = PromptSpec(system="test", user="   ")

    with pytest.raises(llm_gateway.SemanticGatewayError) as exc_info:
        llm_gateway.generate_semantic_response(profile="echo_summary_v1", prompt=prompt)

    assert exc_info.value.code == "semantic_prompt_empty"


def test_generate_semantic_response_raises_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = PromptSpec(system="test", user="Hello world")

    def _fake_execute(**_: object) -> llm_gateway.LlmResult:
        return llm_gateway.LlmResult(text="{invalid", model_used="stub:model")

    monkeypatch.setattr(llm_gateway, "_execute_semantic_request", _fake_execute)

    with pytest.raises(SemanticGatewayError) as exc_info:
        llm_gateway.generate_semantic_response(profile="echo_summary_v1", prompt=prompt)

    assert exc_info.value.code == "semantic_response_invalid_json"
