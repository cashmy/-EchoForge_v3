"""EntryStore gateway implementations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from sqlalchemy import (
    MetaData,
    Table,
    Text,
    and_,
    cast,
    func,
    insert,
    literal_column,
    or_,
    select,
    update,
)
from sqlalchemy.engine import Engine

from ...infra.db import ENGINE
from ...infra.logging import get_logger
from .models import Entry, utcnow
from .pipeline_states import DEFAULT_INGEST_STATE, resolve_next_ingest_state

__all__ = [
    "EntryStoreGateway",
    "FingerprintReadableGateway",
    "InMemoryEntryStoreGateway",
    "PostgresEntryStoreGateway",
    "EntrySearchFilters",
    "EntrySearchResult",
    "build_entry_store_gateway",
]

logger = get_logger(__name__)


@dataclass(frozen=True)
class EntrySearchFilters:
    """Normalized filter set for `/api/entries` queries."""

    terms: tuple[str, ...] = tuple()
    type_ids: tuple[str, ...] = tuple()
    domain_ids: tuple[str, ...] = tuple()
    type_labels: tuple[str, ...] = tuple()
    domain_labels: tuple[str, ...] = tuple()
    pipeline_statuses: tuple[str, ...] = tuple()
    cognitive_statuses: tuple[str, ...] = tuple()
    source_channels: tuple[str, ...] = tuple()
    source_types: tuple[str, ...] = tuple()
    created_from: datetime | None = None
    created_to: datetime | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    include_archived: bool = False
    sort_by: str = "updated_at"
    sort_dir: str = "desc"
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class EntrySearchResult:
    """Container for paginated entry search results."""

    items: List[Entry]
    total: int


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

    def record_extraction_result(
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

    def record_normalization_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Entry: ...

    def record_normalization_failure(
        self,
        entry_id: str,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> Entry: ...

    def save_summary(
        self,
        entry_id: str,
        *,
        summary: str,
        display_title: Optional[str] = None,
        model_used: Optional[str] = None,
        semantic_tags: Optional[List[str]] = None,
    ) -> Entry: ...

    def save_classification(
        self,
        entry_id: str,
        *,
        type_label: str,
        domain_label: str,
        model_used: Optional[str] = None,
    ) -> Entry: ...

    def update_entry_taxonomy(
        self,
        entry_id: str,
        *,
        type_id: Optional[str],
        type_label: Optional[str],
        domain_id: Optional[str],
        domain_label: Optional[str],
        classification_model: Optional[str] = None,
    ) -> Entry: ...

    def record_capture_event(
        self,
        entry_id: str,
        *,
        event_type: str,
        data: Optional[Dict[str, object]] = None,
    ) -> Entry: ...

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Entry: ...

    def get_entry(self, entry_id: str) -> Entry: ...

    def search_entries(self, filters: EntrySearchFilters) -> EntrySearchResult: ...


class FingerprintReadableGateway(Protocol):  # pragma: no cover
    """Minimal lookup interface for idempotency checks."""

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Entry: ...

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
        record = _bootstrap_capture_metadata(record)
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
        updated = _apply_pipeline_transition(record, pipeline_status)
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

    def record_extraction_result(
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
        updated = record.with_extraction_result(
            text=text,
            segments=segments,  # type: ignore[arg-type]
            metadata=metadata,  # type: ignore[arg-type]
            verbatim_path=verbatim_path,
            verbatim_preview=verbatim_preview,
            content_lang=content_lang,
        )
        self._entries[entry_id] = updated
        return updated

    def record_extraction_failure(
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
        updated = record.with_extraction_failure(
            error_code=error_code,
            message=message,
            retryable=retryable,
        )
        self._entries[entry_id] = updated
        return updated

    def record_normalization_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_normalization_result(
            text=text,
            segments=segments,  # type: ignore[arg-type]
            metadata=metadata,  # type: ignore[arg-type]
        )
        self._entries[entry_id] = updated
        return updated

    def record_normalization_failure(
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
        updated = record.with_normalization_failure(
            error_code=error_code,
            message=message,
            retryable=retryable,
        )
        self._entries[entry_id] = updated
        return updated

    def save_summary(
        self,
        entry_id: str,
        *,
        summary: str,
        display_title: Optional[str] = None,
        model_used: Optional[str] = None,
        semantic_tags: Optional[List[str]] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        updated = record.with_summary_result(
            summary=summary,
            display_title=display_title,
            model_used=model_used,
            semantic_tags=semantic_tags,
        )
        self._entries[entry_id] = updated
        return updated

    def save_classification(
        self,
        entry_id: str,
        *,
        type_label: str,
        domain_label: str,
        model_used: Optional[str] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        return self._apply_taxonomy_update(
            record,
            type_id=record.type_id,
            type_label=type_label,
            domain_id=record.domain_id,
            domain_label=domain_label,
            classification_model=model_used,
        )

    def update_entry_taxonomy(
        self,
        entry_id: str,
        *,
        type_id: Optional[str],
        type_label: Optional[str],
        domain_id: Optional[str],
        domain_label: Optional[str],
        classification_model: Optional[str] = None,
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        return self._apply_taxonomy_update(
            record,
            type_id=type_id,
            type_label=type_label,
            domain_id=domain_id,
            domain_label=domain_label,
            classification_model=classification_model,
        )

    def _apply_taxonomy_update(
        self,
        record: Entry,
        *,
        type_id: Optional[str],
        type_label: Optional[str],
        domain_id: Optional[str],
        domain_label: Optional[str],
        classification_model: Optional[str],
    ) -> Entry:
        updated = replace(
            record,
            type_id=type_id,
            type_label=type_label,
            domain_id=domain_id,
            domain_label=domain_label,
            classification_model=(
                classification_model
                if classification_model is not None
                else record.classification_model
            ),
            is_classified=bool(type_label and domain_label),
            updated_at=utcnow(),
        )
        self._entries[record.entry_id] = updated
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

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        if not patch:
            return record
        updated = record.with_capture_metadata(patch=patch)
        self._entries[entry_id] = updated
        return updated

    def get_entry(self, entry_id: str) -> Entry:
        record = self._entries.get(entry_id)
        if record is None:
            raise KeyError(f"Entry {entry_id} not found")
        return record

    def search_entries(self, filters: EntrySearchFilters) -> EntrySearchResult:
        records = list(self._entries.values())
        matching = [
            entry for entry in records if self._match_search_filters(entry, filters)
        ]
        reverse = filters.sort_dir.lower() == "desc"
        matching.sort(
            key=lambda entry: (
                self._sort_value(entry, filters.sort_by),
                entry.entry_id,
            ),
            reverse=reverse,
        )
        start = min(max(filters.offset, 0), len(matching))
        end = min(start + max(filters.limit, 0), len(matching))
        return EntrySearchResult(items=matching[start:end], total=len(matching))

    def _match_search_filters(self, entry: Entry, filters: EntrySearchFilters) -> bool:
        if not filters.include_archived and _entry_is_archived(entry):
            return False
        if filters.type_ids and (entry.type_id or "") not in filters.type_ids:
            return False
        if filters.domain_ids and (entry.domain_id or "") not in filters.domain_ids:
            return False
        if filters.type_labels and not _label_matches(
            entry.type_label, filters.type_labels
        ):
            return False
        if filters.domain_labels and not _label_matches(
            entry.domain_label, filters.domain_labels
        ):
            return False
        if (
            filters.pipeline_statuses
            and entry.pipeline_status not in filters.pipeline_statuses
        ):
            return False
        if (
            filters.cognitive_statuses
            and entry.cognitive_status not in filters.cognitive_statuses
        ):
            return False
        if (
            filters.source_channels
            and entry.source_channel not in filters.source_channels
        ):
            return False
        if filters.source_types and entry.source_type not in filters.source_types:
            return False
        if filters.created_from and entry.created_at < filters.created_from:
            return False
        if filters.created_to and entry.created_at > filters.created_to:
            return False
        if filters.updated_from and entry.updated_at < filters.updated_from:
            return False
        if filters.updated_to and entry.updated_at > filters.updated_to:
            return False
        if filters.terms:
            haystack_parts = [
                entry.display_title or "",
                entry.summary or "",
                entry.verbatim_preview or "",
                entry.normalized_text or "",
                " ".join(entry.semantic_tags or []),
            ]
            haystack = " ".join(part for part in haystack_parts if part).lower()
            if not all(term in haystack for term in filters.terms):
                return False
        return True

    def _sort_value(self, entry: Entry, sort_by: str):
        value = getattr(entry, sort_by, None)
        if isinstance(value, str):
            return value.lower()
        return value


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
        self._is_archived_col = getattr(self._entries.c, "is_archived", None)

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
        entry = _bootstrap_capture_metadata(entry)

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
                capture_metadata=entry.metadata.get("capture_metadata"),
                verbatim_path=entry.verbatim_path,
                verbatim_preview=entry.verbatim_preview,
                content_lang=entry.content_lang,
                transcription_text=entry.transcription_text,
                transcription_segments=entry.transcription_segments,
                transcription_metadata=entry.transcription_metadata,
                transcription_error=entry.transcription_error,
                extracted_text=entry.extracted_text,
                extraction_segments=entry.extraction_segments,
                extraction_metadata=entry.extraction_metadata,
                extraction_error=entry.extraction_error,
                normalized_text=entry.normalized_text,
                normalized_segments=entry.normalized_segments,
                normalization_metadata=entry.normalization_metadata,
                normalization_error=entry.normalization_error,
                summary=entry.summary,
                display_title=entry.display_title,
                summary_model=entry.summary_model,
                type_id=entry.type_id,
                type_label=entry.type_label,
                domain_id=entry.domain_id,
                domain_label=entry.domain_label,
                classification_model=entry.classification_model,
                is_classified=entry.is_classified,
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

    def get_entry(self, entry_id: str) -> Entry:
        with self._engine.begin() as conn:
            row = self._fetch_entry(conn, entry_id)
        return _row_to_entry(row)

    def search_entries(self, filters: EntrySearchFilters) -> EntrySearchResult:
        table = self._entries
        conditions = self._build_search_conditions(filters)
        sort_column = self._resolve_sort_column(filters.sort_by)
        order_clause = (
            sort_column.desc()
            if filters.sort_dir.lower() == "desc"
            else sort_column.asc()
        )
        secondary_order = table.c.entry_id.desc()
        limit_value = max(filters.limit, 1)
        offset_value = max(filters.offset, 0)
        stmt = (
            select(table)
            .where(*conditions)
            .order_by(order_clause, secondary_order)
            .offset(offset_value)
            .limit(limit_value)
        )
        count_stmt = select(func.count()).select_from(table).where(*conditions)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
            total = int(conn.execute(count_stmt).scalar_one())
        return EntrySearchResult(
            items=[_row_to_entry(row) for row in rows],
            total=total,
        )

    def _build_search_conditions(self, filters: EntrySearchFilters) -> tuple:
        c = self._entries.c
        conditions: list[Any] = []
        if filters.type_ids:
            conditions.append(c.type_id.in_(filters.type_ids))
        if filters.domain_ids:
            conditions.append(c.domain_id.in_(filters.domain_ids))
        if filters.type_labels:
            label_exprs = [
                func.lower(c.type_label).like(f"%{label}%")
                for label in filters.type_labels
            ]
            conditions.append(or_(*label_exprs))
        if filters.domain_labels:
            label_exprs = [
                func.lower(c.domain_label).like(f"%{label}%")
                for label in filters.domain_labels
            ]
            conditions.append(or_(*label_exprs))
        if filters.pipeline_statuses:
            conditions.append(c.pipeline_status.in_(filters.pipeline_statuses))
        if filters.cognitive_statuses:
            conditions.append(c.cognitive_status.in_(filters.cognitive_statuses))
        if filters.source_channels:
            conditions.append(c.source_channel.in_(filters.source_channels))
        if filters.source_types:
            conditions.append(c.source_type.in_(filters.source_types))
        if filters.created_from is not None:
            conditions.append(c.created_at >= filters.created_from)
        if filters.created_to is not None:
            conditions.append(c.created_at <= filters.created_to)
        if filters.updated_from is not None:
            conditions.append(c.updated_at >= filters.updated_from)
        if filters.updated_to is not None:
            conditions.append(c.updated_at <= filters.updated_to)
        if not filters.include_archived and self._is_archived_col is not None:
            conditions.append(self._is_archived_col.is_(False))
        if filters.terms:
            searchable_columns = [
                c.display_title,
                c.summary,
                c.verbatim_preview,
                c.normalized_text,
            ]
            semantic_col = getattr(c, "semantic_tags", None)
            if semantic_col is not None:
                searchable_columns.append(cast(semantic_col, Text))
            for term in filters.terms:
                like_value = f"%{term}%"
                term_exprs = [
                    func.lower(column).like(like_value)
                    for column in searchable_columns
                    if column is not None
                ]
                if term_exprs:
                    conditions.append(or_(*term_exprs))
        return tuple(conditions)

    def _resolve_sort_column(self, sort_by: str):
        columns = {
            "created_at": self._entries.c.created_at,
            "updated_at": self._entries.c.updated_at,
            "display_title": self._entries.c.display_title,
            "pipeline_status": self._entries.c.pipeline_status,
            "cognitive_status": self._entries.c.cognitive_status,
        }
        return columns.get(sort_by, self._entries.c.updated_at)

    # ------------------------------------------------------------------
    # Pipeline + transcription updates
    # ------------------------------------------------------------------
    def update_pipeline_status(self, entry_id: str, *, pipeline_status: str) -> Entry:
        with self._engine.begin() as conn:
            current_row = self._fetch_entry(conn, entry_id)
            current_entry = _row_to_entry(current_row)
            updated_entry = _apply_pipeline_transition(current_entry, pipeline_status)
            if updated_entry is current_entry:
                return current_entry
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    pipeline_status=updated_entry.pipeline_status,
                    metadata=updated_entry.metadata,
                    capture_metadata=updated_entry.metadata.get("capture_metadata"),
                    updated_at=updated_entry.updated_at,
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def record_normalization_result(
        self,
        entry_id: str,
        *,
        text: str,
        segments: Optional[List[Dict[str, object]]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            merged_metadata = _merge_metadata(
                current.get("normalization_metadata"), metadata
            )
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    normalized_text=text,
                    normalized_segments=segments,
                    normalization_metadata=merged_metadata,
                    normalization_error=None,
                    updated_at=utcnow(),
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def record_normalization_failure(
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
                normalization_error=failure,
                updated_at=utcnow(),
            )
            .returning(self._entries)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def save_summary(
        self,
        entry_id: str,
        *,
        summary: str,
        display_title: Optional[str] = None,
        model_used: Optional[str] = None,
        semantic_tags: Optional[List[str]] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    summary=summary,
                    display_title=display_title
                    if display_title is not None
                    else current.get("display_title"),
                    summary_model=model_used
                    if model_used is not None
                    else current.get("summary_model"),
                    semantic_tags=semantic_tags
                    if semantic_tags is not None
                    else current.get("semantic_tags"),
                    updated_at=utcnow(),
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def save_classification(
        self,
        entry_id: str,
        *,
        type_label: str,
        domain_label: str,
        model_used: Optional[str] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            classification_model = (
                model_used
                if model_used is not None
                else current.get("classification_model")
            )
            row = self._execute_taxonomy_update(
                conn,
                entry_id,
                type_id=current.get("type_id"),
                type_label=type_label,
                domain_id=current.get("domain_id"),
                domain_label=domain_label,
                classification_model=classification_model,
            )
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def update_entry_taxonomy(
        self,
        entry_id: str,
        *,
        type_id: Optional[str],
        type_label: Optional[str],
        domain_id: Optional[str],
        domain_label: Optional[str],
        classification_model: Optional[str] = None,
    ) -> Entry:
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            classification_value = (
                classification_model
                if classification_model is not None
                else current.get("classification_model")
            )
            row = self._execute_taxonomy_update(
                conn,
                entry_id,
                type_id=type_id,
                type_label=type_label,
                domain_id=domain_id,
                domain_label=domain_label,
                classification_model=classification_value,
            )
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def _execute_taxonomy_update(
        self,
        conn,
        entry_id: str,
        *,
        type_id: Optional[str],
        type_label: Optional[str],
        domain_id: Optional[str],
        domain_label: Optional[str],
        classification_model: Optional[str],
    ):
        stmt = (
            update(self._entries)
            .where(self._entries.c.entry_id == entry_id)
            .values(
                type_id=type_id,
                type_label=type_label,
                domain_id=domain_id,
                domain_label=domain_label,
                classification_model=classification_model,
                is_classified=bool(type_label and domain_label),
                updated_at=utcnow(),
            )
            .returning(self._entries)
        )
        return conn.execute(stmt).mappings().first()

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

    def record_extraction_result(
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
                current.get("extraction_metadata"), metadata
            )
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    extracted_text=text,
                    extraction_segments=segments,
                    extraction_metadata=merged_metadata,
                    extraction_error=None,
                    verbatim_path=verbatim_path
                    if verbatim_path is not None
                    else current.get("verbatim_path"),
                    verbatim_preview=verbatim_preview
                    if verbatim_preview is not None
                    else current.get("verbatim_preview"),
                    content_lang=content_lang
                    if content_lang is not None
                    else current.get("content_lang"),
                    updated_at=utcnow(),
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:  # pragma: no cover - defensive
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def record_extraction_failure(
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
                extraction_error=failure,
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
                .values(
                    metadata=metadata,
                    capture_metadata=metadata.get("capture_metadata"),
                    updated_at=event_timestamp,
                )
                .returning(self._entries)
            )
            row = conn.execute(stmt).mappings().first()
        if row is None:
            raise KeyError(f"Entry {entry_id} not found")
        return _row_to_entry(row)

    def merge_capture_metadata(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
    ) -> Entry:
        if not patch:
            with self._engine.begin() as conn:
                current = self._fetch_entry(conn, entry_id)
            return _row_to_entry(current)
        with self._engine.begin() as conn:
            current = self._fetch_entry(conn, entry_id)
            metadata = dict(current["metadata"] or {})
            capture_meta = _merge_nested_dict(metadata.get("capture_metadata"), patch)
            metadata["capture_metadata"] = capture_meta
            stmt = (
                update(self._entries)
                .where(self._entries.c.entry_id == entry_id)
                .values(
                    metadata=metadata,
                    capture_metadata=capture_meta,
                    updated_at=utcnow(),
                )
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


def _merge_nested_dict(
    existing: Optional[Dict[str, Any]],
    patch: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(existing or {})
    for key, value in patch.items():
        if value is None:
            continue
        current = result.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            result[key] = _merge_nested_dict(current, value)
        else:
            result[key] = value
    return result


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
        extracted_text=row.get("extracted_text"),
        extraction_segments=row.get("extraction_segments"),
        extraction_metadata=dict(row.get("extraction_metadata") or {}),
        extraction_error=row.get("extraction_error"),
        normalized_text=row.get("normalized_text"),
        normalized_segments=row.get("normalized_segments"),
        normalization_metadata=dict(row.get("normalization_metadata") or {}),
        normalization_error=row.get("normalization_error"),
        summary=row.get("summary"),
        display_title=row.get("display_title"),
        summary_model=row.get("summary_model"),
        semantic_tags=row.get("semantic_tags"),
        type_id=row.get("type_id"),
        type_label=row.get("type_label"),
        domain_id=row.get("domain_id"),
        domain_label=row.get("domain_label"),
        classification_model=row.get("classification_model"),
        is_classified=bool(row.get("is_classified")),
    )


def _entry_is_archived(entry: Entry) -> bool:
    metadata = entry.metadata or {}
    if "is_archived" in metadata:
        return bool(metadata.get("is_archived"))
    capture_meta = metadata.get("capture_metadata") or {}
    archived_flag = capture_meta.get("is_archived")
    if archived_flag is None:
        return False
    return bool(archived_flag)


def _label_matches(value: Optional[str], needles: tuple[str, ...]) -> bool:
    if value is None:
        return False
    haystack = value.lower()
    return any(term in haystack for term in needles)


PIPELINE_TRANSITION_EVENT = "pipeline_status_changed"


def _bootstrap_capture_metadata(record: Entry) -> Entry:
    capture_meta = record.metadata.get("capture_metadata") or {}
    if capture_meta.get("ingest_state"):
        return record
    try:
        ingest_state = resolve_next_ingest_state(
            DEFAULT_INGEST_STATE, record.pipeline_status
        )
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"invalid initial pipeline_status '{record.pipeline_status}' for entry {record.entry_id}"
        ) from exc
    timestamp = record.updated_at
    transition_record = {
        "from_ingest_state": None,
        "to_ingest_state": ingest_state,
        "pipeline_status": record.pipeline_status,
        "previous_pipeline_status": None,
        "occurred_at": timestamp.isoformat(),
    }
    return record.with_capture_metadata(
        patch={
            "ingest_state": ingest_state,
            "pipeline_status": record.pipeline_status,
            "pipeline_history": [transition_record],
            "last_transition": transition_record,
        },
        timestamp=timestamp,
    )


def _apply_pipeline_transition(record: Entry, pipeline_status: str) -> Entry:
    current_state = _current_ingest_state(record)
    try:
        next_state = resolve_next_ingest_state(current_state, pipeline_status)
    except ValueError as exc:
        raise ValueError(
            f"pipeline_status '{pipeline_status}' not allowed from ingest_state '{current_state}' for entry {record.entry_id}"
        ) from exc

    if pipeline_status == record.pipeline_status and next_state == current_state:
        return record

    transition_time = utcnow()
    capture_meta = record.metadata.get("capture_metadata") or {}
    history = list(capture_meta.get("pipeline_history") or [])
    transition_record = {
        "from_ingest_state": current_state,
        "to_ingest_state": next_state,
        "pipeline_status": pipeline_status,
        "previous_pipeline_status": record.pipeline_status,
        "occurred_at": transition_time.isoformat(),
    }
    history.append(transition_record)

    updated = record.with_pipeline_status(
        pipeline_status,
        timestamp=transition_time,
    )
    updated = updated.with_capture_metadata(
        patch={
            "ingest_state": next_state,
            "pipeline_status": pipeline_status,
            "pipeline_history": history,
            "last_transition": transition_record,
        },
        timestamp=transition_time,
    )
    updated = updated.with_capture_event(
        event_type=PIPELINE_TRANSITION_EVENT,
        data=transition_record,
        timestamp=transition_time,
    )
    return updated


def _current_ingest_state(record: Entry) -> str:
    capture_meta = record.metadata.get("capture_metadata") or {}
    return capture_meta.get("ingest_state") or DEFAULT_INGEST_STATE
