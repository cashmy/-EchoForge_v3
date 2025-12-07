"""EntryStore gateway implementations."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from sqlalchemy import MetaData, Table, insert, select, update
from sqlalchemy.engine import Engine

from ...infra.db import ENGINE
from ...infra.logging import get_logger
from .models import Entry, utcnow

__all__ = [
    "EntryStoreGateway",
    "FingerprintReadableGateway",
    "InMemoryEntryStoreGateway",
    "PostgresEntryStoreGateway",
    "build_entry_store_gateway",
]

logger = get_logger(__name__)


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

    def record_transcription_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
        verbatim_path: Optional[str] = None,
        verbatim_preview: Optional[str] = None,
        content_lang: Optional[str] = None,
    ) -> Entry: ...

    def record_transcription_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> Entry: ...

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, object]] = None,
    ) -> Entry: ...

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, object]] = None,
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

    def record_transcription_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
        verbatim_path: Optional[str] = None,
        verbatim_preview: Optional[str] = None,
        content_lang: Optional[str] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_transcription_result(
            text=text,
            segments=segments,  # type: ignore[arg-type]
            metadata=metadata,  # type: ignore[arg-type]
            verbatim_path=verbatim_path,
            verbatim_preview=verbatim_preview,
            content_lang=content_lang,
        )
        self._entries[entry_id] = updated
        return updated

    def record_transcription_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_transcription_failure(
            error_code=error_code,
            message=message,
            retryable=retryable,
        )
        self._entries[entry_id] = updated
        return updated

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, object]] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_capture_event(event_type=event_type, data=data)
        self._entries[entry_id] = updated
        return updated

    def get_entry(self, entry_id: str) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        return record


class PostgresEntryStoreGateway(EntryStoreGateway, FingerprintReadableGateway):
    """SQLAlchemy-backed adapter that persists entries to PostgreSQL."""

    def __init__(
        self,
        engine: Optional[Engine] = None,
        *,
        table: Optional[Table] = None,
    ) -> None:
        self._engine = engine or ENGINE
        if table is not None:
            self._entries = table
            self._metadata = table.metadata
        else:
            self._metadata = MetaData()
            self._entries = Table("entries", self._metadata, autoload_with=self._engine)

    # ------------------------------------------------------------------
    # Entry creation + lookups
    # ------------------------------------------------------------------
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
        metadata_dict: Dict[str, Any] = dict(metadata or {})
        fingerprint = metadata_dict.get("capture_fingerprint")
        if not fingerprint:
            raise ValueError("capture_fingerprint is required for EF-01 ingests")

        capture_meta = metadata_dict.get("capture_metadata")
        timestamp = utcnow()
        entry = Entry.new(
            source_type=source_type,
            source_channel=source_channel,
            source_path=source_path,
            metadata=metadata_dict,
            pipeline_status=pipeline_status,
            cognitive_status=cognitive_status,
            timestamp=timestamp,
        )

        insert_stmt = (
            insert(self._entries)
            .values(
                entry_id=entry.entry_id,
                source_type=entry.source_type,
                source_channel=entry.source_channel,
                source_path=entry.source_path,
                pipeline_status=entry.pipeline_status,
                cognitive_status=entry.cognitive_status,
                metadata=entry.metadata,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                capture_fingerprint=fingerprint,
                fingerprint_algo=metadata_dict.get("fingerprint_algo"),
                capture_metadata=capture_meta,
                verbatim_path=entry.verbatim_path,
                verbatim_preview=entry.verbatim_preview,
                content_lang=entry.content_lang,
                transcription_text=entry.transcription_text,
                transcription_segments=entry.transcription_segments,
                transcription_metadata=entry.transcription_metadata,
                transcription_error=entry.transcription_error,
            )
            .returning(self._entries)
        )
        with self._engine.begin() as conn:
            row = conn.execute(insert_stmt).mappings().first()
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("failed to insert entry")
        return _row_to_entry(row)

    def find_by_fingerprint(
        self, fingerprint: str, source_channel: str
    ) -> Optional[Entry]:
        stmt = (
            select(self._entries)
            .where(
                self._entries.c.capture_fingerprint == fingerprint,
                self._entries.c.source_channel == source_channel,
            )
            .limit(1)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            return None
        return _row_to_entry(row)

    # ------------------------------------------------------------------
    # Pipeline + transcription updates
    # ------------------------------------------------------------------
    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str) -> Entry:
        stmt = (
            update(self._entries)
            .where(self._entries.c.entry_id == entry_id)
            .values(pipeline_status=pipeline_status, updated_at=utcnow())
            .returning(self._entries)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def record_transcription_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
        verbatim_path: Optional[str] = None,
        verbatim_preview: Optional[str] = None,
        content_lang: Optional[str] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            merged_metadata = _merge_metadata(
                current["transcription_metadata"], metadata
            )
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    transcription_text=text,
                    transcription_segments=segments,
                    transcription_metadata=merged_metadata,
                    transcription_error=None,
                    verbatim_path=verbatim_path
                    if verbatim_path is not None
                    else current["verbatim_path"],
                    verbatim_preview=verbatim_preview
                    if verbatim_preview is not None
                    else current["verbatim_preview"],
                    content_lang=content_lang
                    if content_lang is not None
                    else current["content_lang"],
                    updated_at=utcnow(),
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:  # pragma: no cover - defensive
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def record_transcription_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> Entry:
        failure = {
            "code": error_code,
            "message": message,
            "retryable": retryable,
        }
        stmt = (
            update(self._entries)
            .where(self._entries.c.entry_id == entry_id)
            .values(
                transcription_error=failure,
                updated_at=utcnow(),
            )
            .returning(self._entries)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    # ------------------------------------------------------------------
    # Capture events
    # ------------------------------------------------------------------
    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, object]] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            metadata = dict(current["metadata"] or {})
            events = list(metadata.get("capture_events") or [])
            event_timestamp = utcnow()
            event: Dict[str, Any] = {
                "type": event_type,
                "timestamp": event_timestamp.isoformat(),
            }
            if data:
                event["data"] = data
            events.append(event)
            metadata["capture_events"] = events
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(metadata=metadata, updated_at=event_timestamp)
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _fetch_entry(self, conn, entry_id: str) -> Mapping[str, Any]:
        stmt = select(self._entries).where(self._entries.c.entry_id == entry_id)
        row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return row


def build_entry_store_gateway(
    *,
    prefer_postgres: bool = True,
    fallback_to_memory: bool = False,
) -> EntryStoreGateway:
    """Factory that returns the desired EntryStore gateway implementation."""

    if prefer_postgres:
        try:
            return PostgresEntryStoreGateway()
        except Exception:
            if not fallback_to_memory:
                raise
            logger.warning(
                "postgres_entry_store_unavailable_falling_back",
                exc_info=True,
            )
    return InMemoryEntryStoreGateway()


def _merge_metadata(
    existing: Optional[Mapping[str, Any]],
    new_metadata: Optional[Dict[str, object]],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(existing or {})
    if new_metadata:
        merged.update(new_metadata)
    return merged


def _row_to_entry(row: Mapping[str, Any]) -> Entry:
    return Entry(
        entry_id=row["entry_id"],
        source_type=row["source_type"],
        source_channel=row["source_channel"],
        source_path=row.get("source_path"),
        pipeline_status=row["pipeline_status"],
        cognitive_status=row["cognitive_status"],
        metadata=dict(row.get("metadata") or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        verbatim_path=row.get("verbatim_path"),
        verbatim_preview=row.get("verbatim_preview"),
        content_lang=row.get("content_lang"),
        transcription_text=row.get("transcription_text"),
        transcription_segments=row.get("transcription_segments"),
        transcription_metadata=dict(row.get("transcription_metadata") or {}),
        transcription_error=row.get("transcription_error"),
    )
