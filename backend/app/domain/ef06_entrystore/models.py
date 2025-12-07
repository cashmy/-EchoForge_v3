"""EF-06 EntryStore data models aligned with EF06 spec v1.1."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

__all__ = [
    "Entry",
    "utcnow",
]


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Entry:
    """Represents a stored Entry row shared across EF components."""

    entry_id: str
    source_type: str
    source_channel: str
    source_path: Optional[str]
    pipeline_status: str
    cognitive_status: str
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    verbatim_path: Optional[str] = None
    verbatim_preview: Optional[str] = None
    content_lang: Optional[str] = None
    transcription_text: Optional[str] = None
    transcription_segments: Optional[List[Dict[str, Any]]] = None
    transcription_metadata: Dict[str, Any] = field(default_factory=dict)
    transcription_error: Optional[Dict[str, Any]] = None

    @classmethod
    def new(
        cls,
        *,
        source_type: str,
        source_channel: str,
        source_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pipeline_status: str = "ingested",
        cognitive_status: str = "unreviewed",
        entry_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        transcription_text: Optional[str] = None,
        transcription_segments: Optional[List[Dict[str, Any]]] = None,
        transcription_metadata: Optional[Dict[str, Any]] = None,
        transcription_error: Optional[Dict[str, Any]] = None,
    ) -> "Entry":
        """Factory that applies EF-06 defaults and generates IDs/timestamps."""

        ts = timestamp or utcnow()
        meta = dict(metadata or {})
        return cls(
            entry_id=entry_id or str(uuid4()),
            source_type=source_type,
            source_channel=source_channel,
            source_path=source_path,
            pipeline_status=pipeline_status,
            cognitive_status=cognitive_status,
            metadata=meta,
            created_at=ts,
            updated_at=ts,
            verbatim_path=None,
            verbatim_preview=None,
            content_lang=None,
            transcription_text=transcription_text,
            transcription_segments=transcription_segments,
            transcription_metadata=dict(transcription_metadata or {}),
            transcription_error=transcription_error,
        )

    def with_pipeline_status(
        self, pipeline_status: str, *, timestamp: Optional[datetime] = None
    ) -> "Entry":
        """Return a copy with refreshed pipeline status and timestamp."""

        return replace(
            self,
            pipeline_status=pipeline_status,
            updated_at=timestamp or utcnow(),
        )

    def with_transcription_result(
        self,
        *,
        text: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        verbatim_path: Optional[str] = None,
        verbatim_preview: Optional[str] = None,
        content_lang: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        merged_metadata = dict(self.transcription_metadata)
        if metadata:
            merged_metadata.update(metadata)
        return replace(
            self,
            transcription_text=text,
            transcription_segments=segments,
            transcription_metadata=merged_metadata,
            transcription_error=None,
            verbatim_path=verbatim_path
            if verbatim_path is not None
            else self.verbatim_path,
            verbatim_preview=verbatim_preview
            if verbatim_preview is not None
            else self.verbatim_preview,
            content_lang=content_lang
            if content_lang is not None
            else self.content_lang,
            updated_at=timestamp or utcnow(),
        )

    def with_transcription_failure(
        self,
        *,
        error_code: str,
        message: str,
        retryable: bool,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        failure = {
            "code": error_code,
            "message": message,
            "retryable": retryable,
        }
        return replace(
            self,
            transcription_error=failure,
            updated_at=timestamp or utcnow(),
        )

    def with_capture_event(
        self,
        *,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        event_timestamp = timestamp or utcnow()
        metadata = dict(self.metadata)
        events = list(metadata.get("capture_events") or [])
        event: Dict[str, Any] = {
            "type": event_type,
            "timestamp": event_timestamp.isoformat(),
        }
        if data:
            event["data"] = data
        events.append(event)
        metadata["capture_events"] = events
        return replace(
            self,
            metadata=metadata,
            updated_at=event_timestamp,
        )
