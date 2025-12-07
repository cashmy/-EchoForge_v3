"""Tests for EF-01 idempotency evaluation helpers."""

# Coverage: EF-01, EF-06

from dataclasses import dataclass

import pytest

from backend.app.domain.ef01_capture.idempotency import (
    IdempotencyDecision,
    evaluate_idempotency,
)
from backend.app.domain.ef06_entrystore.models import Entry

pytestmark = [pytest.mark.ef01, pytest.mark.ef06]


@dataclass
class FakeEntryFingerprintReader:
    result: Entry | None

    def find_by_fingerprint(self, fingerprint: str, source_channel: str):  # noqa: D401
        """Return the configured snapshot regardless of inputs for test simplicity."""

        self.last_query = (fingerprint, source_channel)
        return self.result


def test_evaluate_idempotency_allows_processing_when_no_entry():
    reader = FakeEntryFingerprintReader(result=None)

    decision = evaluate_idempotency(reader, "fp", "watch_folder_audio")

    assert decision == IdempotencyDecision(True, "no_existing_entry", None)


def test_evaluate_idempotency_blocks_when_entry_processing():
    reader = FakeEntryFingerprintReader(
        result=Entry.new(
            entry_id="123",
            pipeline_status="processing",
            metadata={},
            source_type="audio",
            source_channel="watch_folder_audio",
        )
    )

    decision = evaluate_idempotency(reader, "fp", "watch_folder_audio")

    assert decision.should_process is False
    assert decision.reason == "existing_entry_active_or_completed"
    assert decision.existing_entry_id == "123"


def test_evaluate_idempotency_allows_retry_of_failed_entry():
    reader = FakeEntryFingerprintReader(
        result=Entry.new(
            entry_id="123",
            pipeline_status="failed",
            metadata={},
            source_type="audio",
            source_channel="watch_folder_audio",
        )
    )

    decision = evaluate_idempotency(reader, "fp", "watch_folder_audio")

    assert decision.should_process is True
    assert decision.reason == "existing_entry_retry_allowed"
    assert decision.existing_entry_id == "123"


def test_evaluate_idempotency_blocks_when_entry_queued():
    reader = FakeEntryFingerprintReader(
        result=Entry.new(
            entry_id="123",
            pipeline_status="queued_for_transcription",
            metadata={},
            source_type="audio",
            source_channel="watch_folder_audio",
        )
    )

    decision = evaluate_idempotency(reader, "fp", "watch_folder_audio")

    assert decision.should_process is False
    assert decision.reason == "existing_entry_active_or_completed"
