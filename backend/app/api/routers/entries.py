"""EF-07 entry endpoints covering taxonomy patch workflows."""

from __future__ import annotations

import os
import re
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, model_validator

from ...api.dependencies import ActorContext, get_actor_context, get_entry_gateway
from ...domain.ef06_entrystore.gateway import EntryStoreGateway
from ...domain.ef06_entrystore.models import Entry
from ...infra.logging import get_logger
from ...infra.metrics import get_metrics_client

router = APIRouter(prefix="/api/entries", tags=["entries"])
logger = get_logger(__name__)
metrics = get_metrics_client()

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


@router.get("")
def list_entries() -> list[dict[str, str]]:
    return []


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
