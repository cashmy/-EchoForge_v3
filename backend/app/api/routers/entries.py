"""EF-07 entry endpoints covering taxonomy patch workflows."""

from __future__ import annotations

import math
import os
import re
from datetime import datetime
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, model_validator

from ...api.dependencies import ActorContext, get_actor_context, get_entry_gateway
from ...domain.ef06_entrystore.gateway import (
    EntrySearchFilters,
    EntryStoreGateway,
)
from ...domain.ef06_entrystore.models import Entry
from ...domain.ef06_entrystore.pipeline_states import PIPELINE_PHASES
from ...infra.logging import get_logger
from ...infra.metrics import get_metrics_client

router = APIRouter(prefix="/api/entries", tags=["entries"])
logger = get_logger(__name__)
metrics = get_metrics_client()
ALLOW_ENTRY_LABEL_FILTERS = os.getenv("ALLOW_ENTRY_LABEL_FILTERS", "0").lower() in {
    "1",
    "true",
    "yes",
}
MAX_QUERY_LENGTH = 256
MAX_PAGE_SIZE = 100
COGNITIVE_STATUS_VALUES: tuple[str, ...] = (
    "unreviewed",
    "review_needed",
    "processed",
    "complete",
    "needs_more",
)
VALID_PIPELINE_STATUSES: tuple[str, ...] = tuple(
    sorted({status for phase in PIPELINE_PHASES for status in phase.pipeline_statuses})
)
SORTABLE_FIELDS = {
    "created_at",
    "updated_at",
    "display_title",
    "pipeline_status",
    "cognitive_status",
}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")
EntryId = Annotated[str, Path(..., min_length=3, max_length=64)]


class TaxonomyDimensionPatch(BaseModel):
    id: Optional[str] = Field(default=None, description="Canonical taxonomy ID.")
    label: Optional[str] = Field(default=None, description="Human-facing label.")
    clear: bool = Field(
        default=False,
        description="When true, clears the dimension regardless of previous values.",
    )

    @model_validator(mode="after")
    def _validate_payload(self) -> "TaxonomyDimensionPatch":
        if self.clear:
            if self.id not in (None, "") or (
                self.label is not None and self.label.strip()
            ):
                raise ValueError("clear requests cannot include id or label")
            self.id = None
            self.label = None
            return self
        if self.label is None or not self.label.strip():
            raise ValueError("label is required when clear is false")
        self.label = self.label.strip()
        if self.id is not None:
            if not SLUG_PATTERN.fullmatch(self.id):
                raise ValueError("id must be a lowercase slug")
        return self


class TaxonomyPatchBlock(BaseModel):
    type: Optional[TaxonomyDimensionPatch] = None
    domain: Optional[TaxonomyDimensionPatch] = None

    @model_validator(mode="after")
    def _ensure_dimension(self) -> "TaxonomyPatchBlock":
        if self.type is None and self.domain is None:
            raise ValueError("taxonomy patch requires at least one dimension")
        return self


class EntryPatchRequest(BaseModel):
    taxonomy: TaxonomyPatchBlock


class TaxonomyDimensionState(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    pending_reconciliation: bool = False


class EntryTaxonomyState(BaseModel):
    type: TaxonomyDimensionState
    domain: TaxonomyDimensionState


class EntryPatchResponse(BaseModel):
    entry_id: str
    taxonomy: EntryTaxonomyState
    taxonomy_no_change: bool = False


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class EntryListItem(BaseModel):
    entry_id: str
    display_title: Optional[str] = None
    summary: Optional[str] = None
    summary_preview: Optional[str] = None
    pipeline_status: str
    cognitive_status: str
    ingest_state: Optional[str] = None
    type_id: Optional[str] = None
    type_label: Optional[str] = None
    domain_id: Optional[str] = None
    domain_label: Optional[str] = None
    source_type: str
    source_channel: str
    created_at: datetime
    updated_at: datetime
    semantic_tags: List[str] | None = None


class EntryListResponse(BaseModel):
    items: List[EntryListItem] = Field(default_factory=list)
    pagination: PaginationMeta
    filters: Dict[str, object] = Field(default_factory=dict)
    search_applied: bool = False


class EntryDetailResponse(BaseModel):
    entry_id: str
    display_title: Optional[str] = None
    summary: Optional[str] = None
    summary_model: Optional[str] = None
    pipeline_status: str
    cognitive_status: str
    ingest_state: Optional[str] = None
    type_id: Optional[str] = None
    type_label: Optional[str] = None
    domain_id: Optional[str] = None
    domain_label: Optional[str] = None
    source_type: str
    source_channel: str
    source_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    semantic_tags: List[str] | None = None
    metadata: Dict[str, object] = Field(default_factory=dict)
    content_lang: Optional[str] = None
    verbatim_preview: Optional[str] = None
    transcription_text: Optional[str] = None
    transcription_metadata: Dict[str, object] = Field(default_factory=dict)
    extracted_text: Optional[str] = None
    extraction_metadata: Dict[str, object] = Field(default_factory=dict)
    normalized_text: Optional[str] = None
    normalization_metadata: Dict[str, object] = Field(default_factory=dict)


@router.get(
    "/{entry_id}",
    response_model=EntryDetailResponse,
    summary="Retrieve entry detail",
)
def get_entry_detail(
    entry_id: EntryId,
    entry_gateway: EntryStoreGateway = Depends(get_entry_gateway),
) -> EntryDetailResponse:
    try:
        entry = entry_gateway.get_entry(entry_id)
    except KeyError as exc:  # pragma: no cover - defensive
        raise _not_found(entry_id) from exc
    return _serialize_entry_detail(entry)


@router.patch(
    "/{entry_id}",
    response_model=EntryPatchResponse,
    summary="Update entry taxonomy references",
)
def patch_entry_taxonomy(
    entry_id: EntryId,
    payload: EntryPatchRequest,
    entry_gateway: EntryStoreGateway = Depends(get_entry_gateway),
    actor: ActorContext = Depends(get_actor_context),
) -> EntryPatchResponse:
    if not _is_patch_enabled():
        raise _feature_disabled_error()

    metrics.increment("taxonomy_patch_attempt_total")
    try:
        current = entry_gateway.get_entry(entry_id)
    except KeyError as exc:  # pragma: no cover - defensive
        metrics.increment("taxonomy_patch_not_found_total")
        raise _not_found(entry_id) from exc

    changes = payload.taxonomy
    type_id, type_label, type_changed = _apply_dimension_changes(
        current.type_id,
        current.type_label,
        changes.type,
    )
    domain_id, domain_label, domain_changed = _apply_dimension_changes(
        current.domain_id,
        current.domain_label,
        changes.domain,
    )
    if not (type_changed or domain_changed):
        metrics.increment("taxonomy_patch_noop_total")
        return EntryPatchResponse(
            entry_id=current.entry_id,
            taxonomy=_build_taxonomy_state(current),
            taxonomy_no_change=True,
        )

    updated = entry_gateway.update_entry_taxonomy(
        entry_id,
        type_id=type_id,
        type_label=type_label,
        domain_id=domain_id,
        domain_label=domain_label,
    )
    _record_taxonomy_events(entry_gateway, current, updated, actor)
    metrics.increment("taxonomy_patch_success_total")
    logger.info(
        "entry_taxonomy_patch_applied",
        extra={
            "entry_id": entry_id,
            "type_changed": type_changed,
            "domain_changed": domain_changed,
            "actor_id": actor.actor_id,
            "actor_source": actor.actor_source,
            "feature_flag_state": os.getenv("ENABLE_TAXONOMY_PATCH", "0"),
        },
    )
    return EntryPatchResponse(
        entry_id=updated.entry_id,
        taxonomy=_build_taxonomy_state(updated),
    )


@router.get(
    "",
    response_model=EntryListResponse,
    summary="Search and filter entries",
)
def list_entries(
    q: Annotated[
        Optional[str],
        Query(
            description="Free-text search scoped to titles, summaries, and previews.",
        ),
    ] = None,
    type_id: List[str] = Query(default_factory=list),
    domain_id: List[str] = Query(default_factory=list),
    pipeline_status: List[str] = Query(default_factory=list),
    cognitive_status: List[str] = Query(default_factory=list),
    source_channel: List[str] = Query(default_factory=list),
    source_type: List[str] = Query(default_factory=list),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    include_archived: bool = Query(False, description="Include archived entries."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    sort_by: str = Query("updated_at"),
    sort_dir: str = Query("desc"),
    type_label: List[str] = Query(default_factory=list),
    domain_label: List[str] = Query(default_factory=list),
    entry_gateway: EntryStoreGateway = Depends(get_entry_gateway),
) -> EntryListResponse:
    metrics.increment("entries_list_http_total")
    normalized_q = _normalize_query(q)
    type_ids = _normalize_multi_value(type_id, lower=True)
    domain_ids = _normalize_multi_value(domain_id, lower=True)
    type_labels = _normalize_multi_value(type_label, lower=True)
    domain_labels = _normalize_multi_value(domain_label, lower=True)
    pipeline_statuses = _normalize_multi_value(pipeline_status, lower=True)
    cognitive_statuses = _normalize_multi_value(cognitive_status, lower=True)
    source_channels = _normalize_multi_value(source_channel)
    source_types = _normalize_multi_value(source_type)

    if type_labels or domain_labels:
        if not ALLOW_ENTRY_LABEL_FILTERS:
            raise _invalid_request(
                "Label-based filters are disabled in this environment",
                fields={"filters": ["type_label", "domain_label"]},
            )

    _validate_enum_values(
        pipeline_statuses,
        VALID_PIPELINE_STATUSES,
        field_name="pipeline_status",
    )
    _validate_enum_values(
        cognitive_statuses,
        COGNITIVE_STATUS_VALUES,
        field_name="cognitive_status",
    )
    _validate_sorting(sort_by, sort_dir)
    _validate_date_range(created_from, created_to, field="created")
    _validate_date_range(updated_from, updated_to, field="updated")

    offset = (page - 1) * page_size
    filters = EntrySearchFilters(
        terms=_tokenize_query(normalized_q),
        type_ids=type_ids,
        domain_ids=domain_ids,
        type_labels=type_labels if ALLOW_ENTRY_LABEL_FILTERS else tuple(),
        domain_labels=domain_labels if ALLOW_ENTRY_LABEL_FILTERS else tuple(),
        pipeline_statuses=pipeline_statuses,
        cognitive_statuses=cognitive_statuses,
        source_channels=source_channels,
        source_types=source_types,
        created_from=created_from,
        created_to=created_to,
        updated_from=updated_from,
        updated_to=updated_to,
        include_archived=include_archived,
        sort_by=sort_by,
        sort_dir=sort_dir.lower(),
        limit=page_size,
        offset=offset,
    )

    result = entry_gateway.search_entries(filters)
    items = [_serialize_entry(entry) for entry in result.items]
    total_pages = math.ceil(result.total / page_size) if result.total else 0
    response_filters = _build_filter_echo(
        normalized_q,
        type_ids,
        domain_ids,
        pipeline_statuses,
        cognitive_statuses,
        source_channels,
        source_types,
        created_from,
        created_to,
        updated_from,
        updated_to,
        include_archived,
        sort_by,
        sort_dir,
        type_labels,
        domain_labels,
    )
    return EntryListResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=result.total,
            total_pages=total_pages,
        ),
        filters=response_filters,
        search_applied=bool(filters.terms),
    )


def _normalize_query(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:MAX_QUERY_LENGTH]


def _tokenize_query(value: Optional[str]) -> tuple[str, ...]:
    if not value:
        return tuple()
    tokens = [segment.lower() for segment in value.split() if segment.strip()]
    return tuple(tokens)


def _normalize_multi_value(
    values: List[str],
    *,
    lower: bool = False,
) -> tuple[str, ...]:
    normalized: List[str] = []
    seen: set[str] = set()
    for chunk in values:
        parts = chunk.split(",") if chunk else []
        for part in parts:
            cleaned = part.strip()
            if not cleaned:
                continue
            token = cleaned.lower() if lower else cleaned
            if token in seen:
                continue
            normalized.append(token)
            seen.add(token)
    return tuple(normalized)


def _validate_enum_values(
    values: tuple[str, ...],
    allowed: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if not values:
        return
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise _invalid_request(
            f"Invalid {field_name} filters provided",
            fields={field_name: invalid},
        )


def _validate_sorting(sort_by: str, sort_dir: str) -> None:
    if sort_by not in SORTABLE_FIELDS:
        raise _invalid_request(
            "Unsupported sort field",
            fields={"sort_by": sort_by},
        )
    if sort_dir.lower() not in {"asc", "desc"}:
        raise _invalid_request(
            "sort_dir must be 'asc' or 'desc'",
            fields={"sort_dir": sort_dir},
        )


def _validate_date_range(
    start: Optional[datetime],
    end: Optional[datetime],
    *,
    field: str,
) -> None:
    if start and end and start > end:
        raise _invalid_request(
            f"{field.capitalize()}_from must be before {field}_to",
            fields={f"{field}_range": f"{start.isoformat()} - {end.isoformat()}"},
        )


def _build_filter_echo(
    query: Optional[str],
    type_ids: tuple[str, ...],
    domain_ids: tuple[str, ...],
    pipeline_statuses: tuple[str, ...],
    cognitive_statuses: tuple[str, ...],
    source_channels: tuple[str, ...],
    source_types: tuple[str, ...],
    created_from: Optional[datetime],
    created_to: Optional[datetime],
    updated_from: Optional[datetime],
    updated_to: Optional[datetime],
    include_archived: bool,
    sort_by: str,
    sort_dir: str,
    type_labels: tuple[str, ...],
    domain_labels: tuple[str, ...],
) -> Dict[str, object]:
    payload: Dict[str, object] = {}
    if query:
        payload["q"] = query
    if type_ids:
        payload["type_id"] = list(type_ids)
    if domain_ids:
        payload["domain_id"] = list(domain_ids)
    if pipeline_statuses:
        payload["pipeline_status"] = list(pipeline_statuses)
    if cognitive_statuses:
        payload["cognitive_status"] = list(cognitive_statuses)
    if source_channels:
        payload["source_channel"] = list(source_channels)
    if source_types:
        payload["source_type"] = list(source_types)
    if created_from:
        payload["created_from"] = created_from
    if created_to:
        payload["created_to"] = created_to
    if updated_from:
        payload["updated_from"] = updated_from
    if updated_to:
        payload["updated_to"] = updated_to
    if type_labels:
        payload["type_label"] = list(type_labels)
    if domain_labels:
        payload["domain_label"] = list(domain_labels)
    payload["include_archived"] = include_archived
    payload["sort_by"] = sort_by
    payload["sort_dir"] = sort_dir.lower()
    return payload


def _serialize_entry(entry: Entry) -> EntryListItem:
    summary_preview = entry.summary or entry.verbatim_preview
    semantic_tags = list(entry.semantic_tags or []) if entry.semantic_tags else None
    return EntryListItem(
        entry_id=entry.entry_id,
        display_title=entry.display_title,
        summary=entry.summary,
        summary_preview=summary_preview,
        pipeline_status=entry.pipeline_status,
        cognitive_status=entry.cognitive_status,
        ingest_state=_extract_ingest_state(entry),
        type_id=entry.type_id,
        type_label=entry.type_label,
        domain_id=entry.domain_id,
        domain_label=entry.domain_label,
        source_type=entry.source_type,
        source_channel=entry.source_channel,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        semantic_tags=semantic_tags,
    )


def _serialize_entry_detail(entry: Entry) -> EntryDetailResponse:
    semantic_tags = list(entry.semantic_tags or []) if entry.semantic_tags else None
    return EntryDetailResponse(
        entry_id=entry.entry_id,
        display_title=entry.display_title,
        summary=entry.summary,
        summary_model=entry.summary_model,
        pipeline_status=entry.pipeline_status,
        cognitive_status=entry.cognitive_status,
        ingest_state=_extract_ingest_state(entry),
        type_id=entry.type_id,
        type_label=entry.type_label,
        domain_id=entry.domain_id,
        domain_label=entry.domain_label,
        source_type=entry.source_type,
        source_channel=entry.source_channel,
        source_path=entry.source_path,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        semantic_tags=semantic_tags,
        metadata=dict(entry.metadata or {}),
        content_lang=entry.content_lang,
        verbatim_preview=entry.verbatim_preview,
        transcription_text=entry.transcription_text,
        transcription_metadata=dict(entry.transcription_metadata or {}),
        extracted_text=entry.extracted_text,
        extraction_metadata=dict(entry.extraction_metadata or {}),
        normalized_text=entry.normalized_text,
        normalization_metadata=dict(entry.normalization_metadata or {}),
    )


def _extract_ingest_state(entry: Entry) -> Optional[str]:
    metadata = entry.metadata or {}
    capture_meta = metadata.get("capture_metadata") or {}
    ingest_state = capture_meta.get("ingest_state")
    if isinstance(ingest_state, str):
        return ingest_state
    return None


def _invalid_request(
    message: str,
    *,
    fields: Dict[str, object] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error_code": "EF07-INVALID-REQUEST",
            "message": message,
            "details": fields or {},
        },
    )


def _is_patch_enabled() -> bool:
    return os.getenv("ENABLE_TAXONOMY_PATCH", "0").lower() in {"1", "true", "yes"}


def _feature_disabled_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "EF07-FEATURE-DISABLED",
            "message": "Taxonomy patch API is disabled",
            "details": {"feature": "enable_taxonomy_patch"},
        },
    )


def _not_found(entry_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "EF07-NOT-FOUND",
            "message": f"Entry '{entry_id}' not found",
            "details": {"entry_id": entry_id},
        },
    )


def _apply_dimension_changes(
    current_id: Optional[str],
    current_label: Optional[str],
    mutation: Optional[TaxonomyDimensionPatch],
) -> tuple[Optional[str], Optional[str], bool]:
    if mutation is None:
        return current_id, current_label, False
    if mutation.clear:
        changed = current_id is not None or current_label is not None
        return None, None, changed
    changed = (current_id or None) != (mutation.id or None) or (
        current_label or None
    ) != mutation.label
    return mutation.id, mutation.label, changed


def _build_taxonomy_state(entry: Entry) -> EntryTaxonomyState:
    return EntryTaxonomyState(
        type=_dimension_state(entry.type_id, entry.type_label),
        domain=_dimension_state(entry.domain_id, entry.domain_label),
    )


def _dimension_state(
    taxonomy_id: Optional[str],
    label: Optional[str],
) -> TaxonomyDimensionState:
    return TaxonomyDimensionState(
        id=taxonomy_id,
        label=label,
        pending_reconciliation=bool(label and not taxonomy_id),
    )


def _record_taxonomy_events(
    entry_gateway: EntryStoreGateway,
    before: Entry,
    after: Entry,
    actor: ActorContext,
) -> None:
    for dimension in ("type", "domain"):
        before_state = {
            "id": getattr(before, f"{dimension}_id"),
            "label": getattr(before, f"{dimension}_label"),
        }
        after_state = {
            "id": getattr(after, f"{dimension}_id"),
            "label": getattr(after, f"{dimension}_label"),
        }
        if before_state == after_state:
            continue
        event_type = (
            "taxonomy.reference.cleared"
            if after_state["id"] is None and after_state["label"] is None
            else "taxonomy.reference.updated"
        )
        entry_gateway.record_capture_event(
            after.entry_id,
            event_type=event_type,
            data={
                "dimension": dimension,
                "before": before_state,
                "after": after_state,
                "actor_id": actor.actor_id,
                "actor_source": actor.actor_source,
            },
        )
