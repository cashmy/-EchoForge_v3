"""Taxonomy service orchestrating validation + persistence."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict

from ...infra.events import EventEmitter, get_event_emitter
from ...infra.logging import get_logger
from ...infra.metrics import MetricsClient, get_metrics_client
from .repository import InMemoryTaxonomyRepository, TaxonomyRepository
from .types import (
    TaxonomyKind,
    TaxonomyListResult,
    TaxonomyRow,
    TaxonomyServiceError,
    utcnow,
)

logger = get_logger(__name__)

DEFAULT_ACTOR_ID = "system"
DEFAULT_ACTOR_SOURCE = "taxonomy_service"


class TaxonomyService:
    """Validation + governance layer over taxonomy persistence."""

    def __init__(
        self,
        *,
        allow_hard_delete: bool = False,
        repository: TaxonomyRepository | None = None,
        event_emitter: EventEmitter | None = None,
        metrics: MetricsClient | None = None,
    ) -> None:
        self._allow_hard_delete = allow_hard_delete
        self._repository = repository or InMemoryTaxonomyRepository()
        self._event_emitter = event_emitter or get_event_emitter()
        self._metrics = metrics or get_metrics_client()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def list(
        self,
        kind: TaxonomyKind,
        *,
        page: int,
        page_size: int,
        sort_by: str | None,
        sort_dir: str | None,
        active: bool | None,
        updated_after: datetime | None,
    ) -> TaxonomyListResult:
        return self._repository.list(
            kind,
            page=page,
            page_size=page_size,
            sort_by=sort_by or "sort_order",
            sort_dir=sort_dir or "asc",
            active=active,
            updated_after=updated_after,
        )

    def create(
        self,
        kind: TaxonomyKind,
        payload: Dict[str, Any],
        *,
        actor_id: str | None = None,
        actor_source: str | None = None,
    ) -> TaxonomyRow:
        normalized = self._normalize_payload(kind, payload, is_update=False)
        row = self._repository.create(kind, normalized)
        actor = self._actor_context(actor_id, actor_source)
        self._emit_taxonomy_event(
            kind=kind,
            action="created",
            before=None,
            after=row,
            actor=actor,
        )
        self._refresh_active_metric(kind)
        logger.info(
            "taxonomy_create",
            extra={
                "kind": kind.value,
                "id": row.id,
                "actor_id": actor["actor_id"],
            },
        )
        return row

    def update(
        self,
        kind: TaxonomyKind,
        *,
        taxonomy_id: str,
        payload: Dict[str, Any],
        actor_id: str | None = None,
        actor_source: str | None = None,
    ) -> TaxonomyRow:
        before = self._repository.get(kind, taxonomy_id)
        normalized = self._normalize_payload(kind, payload, is_update=True)
        updated = self._repository.update(
            kind,
            taxonomy_id=taxonomy_id,
            payload=normalized,
        )
        actor = self._actor_context(actor_id, actor_source)
        action = self._resolve_update_action(before, updated)
        self._emit_taxonomy_event(
            kind=kind,
            action=action,
            before=before,
            after=updated,
            actor=actor,
        )
        if action in {"deactivated", "reactivated"}:
            self._refresh_active_metric(kind)
        logger.info(
            "taxonomy_update",
            extra={
                "kind": kind.value,
                "id": taxonomy_id,
                "action": action,
                "actor_id": actor["actor_id"],
            },
        )
        return updated

    def delete(
        self,
        kind: TaxonomyKind,
        *,
        taxonomy_id: str,
        actor_id: str | None = None,
        actor_source: str | None = None,
    ) -> TaxonomyRow:
        actor = self._actor_context(actor_id, actor_source)
        if not self._allow_hard_delete:
            self._safe_metrics_increment("taxonomy_delete_blocked_total")
            raise TaxonomyServiceError(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                error_code="EF07-HARD-DELETE-DISABLED",
                message="Hard delete disabled for this deployment",
                details={"reason": "hard_delete_disabled"},
            )
        row = self._repository.delete(kind, taxonomy_id=taxonomy_id)
        self._emit_taxonomy_event(
            kind=kind,
            action="deleted",
            before=row,
            after=None,
            actor=actor,
        )
        self._refresh_active_metric(kind)
        logger.warning(
            "taxonomy_delete",
            extra={
                "kind": kind.value,
                "id": taxonomy_id,
                "referenced_entries": row.referenced_entries,
                "actor_id": actor["actor_id"],
            },
        )
        return row

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_payload(
        self,
        kind: TaxonomyKind,
        payload: Dict[str, Any],
        *,
        is_update: bool,
    ) -> Dict[str, Any]:
        normalized = dict(payload)
        if not is_update:
            taxonomy_id = normalized.get("id")
            if taxonomy_id is None or not str(taxonomy_id).strip():
                self._invalid_request("id is required", details={"field": "id"})
            normalized["id"] = str(taxonomy_id).strip()
        if not is_update:
            normalized.setdefault("name", normalized.get("id"))
            normalized.setdefault("active", True)
            normalized.setdefault("sort_order", 500)
        if "label" in normalized and normalized["label"] is not None:
            normalized["label"] = str(normalized["label"]).strip()
            if not normalized["label"]:
                self._invalid_request("label is required", details={"field": "label"})
        if "name" in normalized and normalized["name"] is not None:
            normalized["name"] = str(normalized["name"]).strip()
            if not normalized["name"]:
                self._invalid_request(
                    "name must be a non-empty string",
                    details={"field": "name"},
                )
        sort_order = normalized.get("sort_order")
        if sort_order is not None:
            sort_value = int(sort_order)
            if not 0 <= sort_value <= 10_000:
                self._invalid_request(
                    "sort_order must be between 0 and 10000",
                    details={"field": "sort_order"},
                )
            normalized["sort_order"] = sort_value
        if "metadata" in normalized and normalized["metadata"] is not None:
            metadata = normalized["metadata"]
            if not isinstance(metadata, dict):
                self._invalid_request(
                    "metadata must be an object",
                    details={"field": "metadata"},
                )
            normalized["metadata"] = dict(metadata)
        if kind is TaxonomyKind.DOMAIN:
            metadata = normalized.get("metadata") or {}
            parent = metadata.get("parent_domain_id")
            if parent not in (None, ""):
                raise TaxonomyServiceError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    error_code="EF07-INVALID-REQUEST",
                    message="parent_domain_id is reserved for future versions",
                )
        return normalized

    @staticmethod
    def _resolve_update_action(before: TaxonomyRow, after: TaxonomyRow) -> str:
        if before.active and not after.active:
            return "deactivated"
        if not before.active and after.active:
            return "reactivated"
        return "updated"

    def _actor_context(
        self,
        actor_id: str | None,
        actor_source: str | None,
    ) -> Dict[str, str]:
        return {
            "actor_id": actor_id or DEFAULT_ACTOR_ID,
            "actor_source": actor_source or DEFAULT_ACTOR_SOURCE,
        }

    def _emit_taxonomy_event(
        self,
        *,
        kind: TaxonomyKind,
        action: str,
        before: TaxonomyRow | None,
        after: TaxonomyRow | None,
        actor: Dict[str, str],
    ) -> None:
        row = after or before
        if row is None:
            return
        payload = {
            "taxonomy_id": row.id,
            "resource": kind.value,
            "action": action,
            "actor_id": actor["actor_id"],
            "actor_source": actor["actor_source"],
            "changes": self._build_changes(before, after),
            "referenced_entries": row.referenced_entries,
            "allow_taxonomy_delete": self._allow_hard_delete,
            "occurred_at": utcnow().isoformat(),
        }
        topic = f"taxonomy.{kind.value}.{action}"
        try:
            self._event_emitter.emit(topic, payload)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "taxonomy_event_emit_failed",
                extra={"topic": topic, "taxonomy_id": row.id},
            )
        self._record_mutation_metric(kind, action)

    def _build_changes(
        self,
        before: TaxonomyRow | None,
        after: TaxonomyRow | None,
    ) -> Dict[str, Any]:
        before_snapshot = self._row_snapshot(before)
        after_snapshot = self._row_snapshot(after)
        delta: Dict[str, Any] = {}
        keys = (
            "name",
            "label",
            "description",
            "active",
            "sort_order",
            "metadata",
        )
        for key in keys:
            before_value = (before_snapshot or {}).get(key)
            after_value = (after_snapshot or {}).get(key)
            if before_value != after_value:
                delta[key] = {"before": before_value, "after": after_value}
        return {
            "before": before_snapshot,
            "after": after_snapshot,
            "delta": delta,
        }

    @staticmethod
    def _row_snapshot(row: TaxonomyRow | None) -> Dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "label": row.label,
            "description": row.description,
            "active": row.active,
            "sort_order": row.sort_order,
            "metadata": dict(row.metadata or {}),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "referenced_entries": row.referenced_entries,
        }

    def _record_mutation_metric(self, kind: TaxonomyKind, action: str) -> None:
        metric = f"taxonomy_{kind.value}_{action}_total"
        self._safe_metrics_increment(metric)

    def _refresh_active_metric(self, kind: TaxonomyKind) -> None:
        try:
            snapshot = self._repository.list(
                kind,
                page=1,
                page_size=1,
                sort_by="sort_order",
                sort_dir="asc",
                active=True,
                updated_after=None,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "taxonomy_active_metric_refresh_failed",
                extra={"resource": kind.value},
            )
            return
        metric = f"taxonomy_{kind.value}_active_total"
        self._safe_metrics_gauge(metric, snapshot.total_items)

    def _safe_metrics_increment(self, metric: str, value: int = 1) -> None:
        try:
            self._metrics.increment(metric, value)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "metrics_increment_failed",
                extra={"metric": metric, "value": value},
            )

    def _safe_metrics_gauge(self, metric: str, value: int) -> None:
        try:
            self._metrics.gauge(metric, value)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "metrics_gauge_failed",
                extra={"metric": metric, "value": value},
            )

    @staticmethod
    def _invalid_request(
        message: str,
        *,
        details: Dict[str, Any] | None = None,
    ) -> None:
        raise TaxonomyServiceError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code="EF07-INVALID-REQUEST",
            message=message,
            details=details or {},
        )

    @staticmethod
    def _not_found(kind: TaxonomyKind, taxonomy_id: str) -> TaxonomyServiceError:
        return TaxonomyServiceError(
            status_code=HTTPStatus.NOT_FOUND,
            error_code="EF07-NOT-FOUND",
            message=f"{kind.value.title()} '{taxonomy_id}' not found",
            details={"id": taxonomy_id},
        )
