"""EntryStore gateway implementations."""

from __future__ import annotations

from typing import Dict, Optional, Protocol, Tuple

from .models import Entry, utcnow

__all__ = [
    "EntryStoreGateway",
    "FingerprintReadableGateway",
    "InMemoryEntryStoreGateway",
]


class EntryStoreGateway(Protocol):  # pragma: no cover
    """Abstraction EF-01 relies on to create Entry records."""

    def create_entry(
        self,
        *,
        source_type: str,
        source_channel: str,
        source_path: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
        pipeline_status: str = "ingested",
        cognitive_status: str = "unreviewed",
    ) -> Entry: ...

    def update_pipeline_status(
        self, entry_id: str, *, pipeline_status: str
    ) -> Entry: ...


class FingerprintReadableGateway(Protocol):  # pragma: no cover
    """Minimal lookup interface for idempotency checks."""

    def find_by_fingerprint(
        self, fingerprint: str, source_channel: str
    ) -> Optional[Entry]: ...


class InMemoryEntryStoreGateway(EntryStoreGateway, FingerprintReadableGateway):
    """Simple in-memory EntryStore used for local development and tests."""

    def __init__(self) -> None:
        self._entries: Dict[str, Entry] = {}
        self._fingerprint_index: Dict[Tuple[str, str], str] = {}

    def create_entry(
        self,
        *,
        source_type: str,
        source_channel: str,
        source_path: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
        pipeline_status: str = "ingested",
        cognitive_status: str = "unreviewed",
    ) -> Entry:
        metadata = metadata or {}
        fingerprint = metadata.get("capture_fingerprint")
        if not fingerprint:
            raise ValueError("capture_fingerprint is required for EF-01 ingests")

        record = Entry.new(
            source_type=source_type,
            source_channel=source_channel,
            source_path=source_path,
            metadata=metadata,
            pipeline_status=pipeline_status,
            cognitive_status=cognitive_status,
            timestamp=utcnow(),
        )
        self._entries[record.entry_id] = record
        self._fingerprint_index[(fingerprint, source_channel)] = record.entry_id
        return record

    def find_by_fingerprint(
        self, fingerprint: str, source_channel: str
    ) -> Optional[Entry]:
        entry_id = self._fingerprint_index.get((fingerprint, source_channel))
        if not entry_id:
            return None
        return self._entries[entry_id]

    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_pipeline_status(pipeline_status)
        self._entries[entry_id] = updated
        return updated
