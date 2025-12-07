"""Idempotency evaluation helpers for EF-01 capture flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..ef06_entrystore.models import Entry

__all__ = [
    "EntryFingerprintReader",
    "IdempotencyDecision",
    "SKIP_PIPELINE_STATUSES",
    "evaluate_idempotency",
]


class EntryFingerprintReader(Protocol):
    """Minimal interface EF-01 needs from EF-06 for idempotency checks."""

    def find_by_fingerprint(
        self, fingerprint: str, source_channel: str
    ) -> "Entry | None":  # pragma: no cover - structural typing hook
        ...


@dataclass(frozen=True)
class IdempotencyDecision:
    """Represents the outcome of an idempotency lookup."""

    should_process: bool
    reason: str
    existing_entry_id: str | None = None


SKIP_PIPELINE_STATUSES = {
    "queued_for_transcription",
    "queued_for_extraction",
    "queued",
    "processing",
    "processed",
}


def evaluate_idempotency(
    store_reader: EntryFingerprintReader,
    fingerprint: str,
    source_channel: str,
) -> IdempotencyDecision:
    """Lookup EF-06 to decide whether EF-01 should ingest the capture event."""

    snapshot = store_reader.find_by_fingerprint(fingerprint, source_channel)
    if snapshot is None:
        return IdempotencyDecision(True, "no_existing_entry")

    if snapshot.pipeline_status in SKIP_PIPELINE_STATUSES:
        return IdempotencyDecision(
            False,
            "existing_entry_active_or_completed",
            existing_entry_id=snapshot.entry_id,
        )

    return IdempotencyDecision(
        True,
        "existing_entry_retry_allowed",
        existing_entry_id=snapshot.entry_id,
    )
