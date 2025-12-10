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
    extracted_text: Optional[str] = None
    extraction_segments: Optional[List[Dict[str, Any]]] = None
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_error: Optional[Dict[str, Any]] = None
    normalized_text: Optional[str] = None
    normalized_segments: Optional[List[Dict[str, Any]]] = None
    normalization_metadata: Dict[str, Any] = field(default_factory=dict)
    normalization_error: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    display_title: Optional[str] = None
    summary_model: Optional[str] = None
    semantic_tags: Optional[List[str]] = None
    type_id: Optional[str] = None
    type_label: Optional[str] = None
    domain_id: Optional[str] = None
    domain_label: Optional[str] = None
    classification_model: Optional[str] = None
    is_classified: bool = False

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
        extracted_text: Optional[str] = None,
        extraction_segments: Optional[List[Dict[str, Any]]] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        extraction_error: Optional[Dict[str, Any]] = None,
        normalized_text: Optional[str] = None,
        normalized_segments: Optional[List[Dict[str, Any]]] = None,
        normalization_metadata: Optional[Dict[str, Any]] = None,
        normalization_error: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        display_title: Optional[str] = None,
        summary_model: Optional[str] = None,
        semantic_tags: Optional[List[str]] = None,
        type_id: Optional[str] = None,
        type_label: Optional[str] = None,
        domain_id: Optional[str] = None,
        domain_label: Optional[str] = None,
        classification_model: Optional[str] = None,
        is_classified: bool = False,
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
            extracted_text=extracted_text,
            extraction_segments=extraction_segments,
            extraction_metadata=dict(extraction_metadata or {}),
            extraction_error=extraction_error,
            normalized_text=normalized_text,
            normalized_segments=normalized_segments,
            normalization_metadata=dict(normalization_metadata or {}),
            normalization_error=normalization_error,
            summary=summary,
            display_title=display_title,
            summary_model=summary_model,
            semantic_tags=list(semantic_tags) if semantic_tags else None,
            type_id=type_id,
            type_label=type_label,
            domain_id=domain_id,
            domain_label=domain_label,
            classification_model=classification_model,
            is_classified=is_classified,
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

    def with_capture_metadata(
        self,
        *,
        patch: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        if not patch:
            return self
        metadata = dict(self.metadata)
        existing = dict(metadata.get("capture_metadata") or {})
        metadata["capture_metadata"] = _deep_merge_dict(existing, patch)
        return replace(
            self,
            metadata=metadata,
            updated_at=timestamp or utcnow(),
        )

    def with_extraction_result(
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
        merged_metadata = dict(self.extraction_metadata)
        if metadata:
            merged_metadata.update(metadata)
        return replace(
            self,
            extracted_text=text,
            extraction_segments=segments,
            extraction_metadata=merged_metadata,
            extraction_error=None,
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

    def with_extraction_failure(
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
            extraction_error=failure,
            updated_at=timestamp or utcnow(),
        )

    def with_normalization_result(
        self,
        *,
        text: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        merged_metadata = dict(self.normalization_metadata)
        if metadata:
            merged_metadata.update(metadata)
        return replace(
            self,
            normalized_text=text,
            normalized_segments=segments,
            normalization_metadata=merged_metadata,
            normalization_error=None,
            updated_at=timestamp or utcnow(),
        )

    def with_normalization_failure(
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
            normalization_error=failure,
            updated_at=timestamp or utcnow(),
        )

    def with_summary_result(
        self,
        *,
        summary: str,
        display_title: Optional[str] = None,
        model_used: Optional[str] = None,
        semantic_tags: Optional[List[str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        preview_value = self.verbatim_preview
        if (preview_value is None or preview_value == "") and summary:
            preview_value = summary[:400]
        return replace(
            self,
            summary=summary,
            display_title=display_title or self.display_title,
            summary_model=model_used or self.summary_model,
            semantic_tags=list(semantic_tags)
            if semantic_tags is not None
            else self.semantic_tags,
            verbatim_preview=preview_value,
            updated_at=timestamp or utcnow(),
        )

    def with_classification_result(
        self,
        *,
        type_label: str,
        domain_label: str,
        model_used: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "Entry":
        return replace(
            self,
            type_label=type_label,
            domain_label=domain_label,
            classification_model=model_used or self.classification_model,
            is_classified=True,
            updated_at=timestamp or utcnow(),
        )


def _deep_merge_dict(
    original: Dict[str, Any],
    patch: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(original)
    for key, value in patch.items():
        if value is None:
            continue
        existing = result.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            result[key] = _deep_merge_dict(existing, value)
        else:
            result[key] = value
    return result
