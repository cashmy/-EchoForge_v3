"""ETS scenarios for taxonomy CRUD + EntryStore resilience."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_entry_gateway, get_taxonomy_service
from backend.app.api.routers import entries, taxonomy
from backend.app.domain.ef06_entrystore.gateway import InMemoryEntryStoreGateway
from backend.app.domain.taxonomy import (
    InMemoryTaxonomyRepository,
    TaxonomyKind,
    TaxonomyService,
)
from backend.app.infra.events import EventEmitter
from backend.app.infra.metrics import MetricsClient

pytestmark = [pytest.mark.ets_taxonomy, pytest.mark.ef06, pytest.mark.ef07]


class RecordingEmitter(EventEmitter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def emit(self, topic: str, payload: dict[str, Any]) -> None:  # type: ignore[override]
        self.calls.append((topic, payload))


class RecordingMetrics(MetricsClient):
    def __init__(self) -> None:
        self.increments: list[tuple[str, int]] = []
        self.gauges: list[tuple[str, int]] = []

    def increment(self, metric: str, value: int = 1) -> None:  # type: ignore[override]
        self.increments.append((metric, value))

    def gauge(self, metric: str, value: int) -> None:  # type: ignore[override]
        self.gauges.append((metric, value))


def _build_service(
    *, allow_hard_delete: bool = True
) -> tuple[
    TaxonomyService,
    InMemoryTaxonomyRepository,
    RecordingEmitter,
    RecordingMetrics,
]:
    repository = InMemoryTaxonomyRepository()
    emitter = RecordingEmitter()
    metrics = RecordingMetrics()
    service = TaxonomyService(
        allow_hard_delete=allow_hard_delete,
        repository=repository,
        event_emitter=emitter,
        metrics=metrics,
    )
    return service, repository, emitter, metrics


def _build_client(
    service: TaxonomyService,
    gateway: InMemoryEntryStoreGateway | None = None,
) -> tuple[TestClient, InMemoryEntryStoreGateway]:
    app = FastAPI()
    app.include_router(taxonomy.router)
    app.include_router(entries.router)
    storage = gateway or InMemoryEntryStoreGateway()
    app.dependency_overrides[get_taxonomy_service] = lambda: service
    app.dependency_overrides[get_entry_gateway] = lambda: storage
    return TestClient(app), storage


def test_ets_api_taxonomy_crud_flow():
    service, repository, emitter, metrics = _build_service(allow_hard_delete=True)
    client, _gateway = _build_client(service)
    headers = {"X-Actor-Id": "ets", "X-Actor-Source": "suite"}

    create_type = client.post(
        "/api/types",
        json={"id": "project_note", "label": "Project Note"},
        headers=headers,
    )
    assert create_type.status_code == 201

    create_domain = client.post(
        "/api/domains",
        json={"id": "ops", "label": "Operations"},
        headers=headers,
    )
    assert create_domain.status_code == 201

    list_resp = client.get("/api/types")
    assert list_resp.status_code == 200
    assert list_resp.json()["total_items"] == 1

    deactivate = client.patch(
        "/api/types/project_note",
        json={"active": False, "description": "Legacy"},
        headers=headers,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["active"] is False

    active_list = client.get("/api/types", params={"active": True})
    assert active_list.json()["total_items"] == 0

    inactive_list = client.get("/api/types", params={"active": False})
    assert inactive_list.json()["total_items"] == 1

    reactivate = client.patch(
        "/api/types/project_note",
        json={"active": True},
        headers=headers,
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["active"] is True

    # Domain delete returns 204 when no references exist
    delete_domain = client.delete("/api/domains/ops", headers=headers)
    assert delete_domain.status_code == 204

    # Simulate referenced entries -> delete warns instead of blind drop
    repository._store[TaxonomyKind.TYPE]["project_note"].referenced_entries = 2  # type: ignore[attr-defined]
    delete_type = client.delete("/api/types/project_note", headers=headers)
    assert delete_type.status_code == 200
    assert delete_type.json() == {"deletion_warning": True, "referenced_entries": 2}

    topics = [topic for topic, _payload in emitter.calls]
    assert "taxonomy.type.created" in topics
    assert "taxonomy.type.deactivated" in topics
    assert "taxonomy.type.reactivated" in topics
    assert "taxonomy.type.deleted" in topics
    assert ("taxonomy_type_created_total", 1) in metrics.increments
    assert any(
        metric[0] == "taxonomy_type_deleted_total" for metric in metrics.increments
    )


def test_ets_db_taxonomy_reference_cleanup_flow(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_TAXONOMY_PATCH", "1")
    service, repository, _emitter, _metrics = _build_service(allow_hard_delete=True)
    client, gateway = _build_client(service)
    headers = {"X-Actor-Id": "ets", "X-Actor-Source": "suite"}

    client.post(
        "/api/types",
        json={"id": "architecture_note", "label": "Architecture"},
        headers=headers,
    )
    client.post(
        "/api/domains", json={"id": "platform", "label": "Platform"}, headers=headers
    )

    entry = gateway.create_entry(
        source_type="document",
        source_channel="manual_text",
        source_path="/tmp/ets-taxonomy.txt",
        metadata={
            "capture_fingerprint": "ets-taxonomy-entry",
            "fingerprint_algo": "sha256",
        },
    )

    patch_resp = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={
            "taxonomy": {
                "type": {"id": "architecture_note", "label": "Architecture"},
                "domain": {"id": "platform", "label": "Platform"},
            }
        },
        headers=headers,
    )
    assert patch_resp.status_code == 200

    repository._store[TaxonomyKind.TYPE]["architecture_note"].referenced_entries = 1  # type: ignore[attr-defined]
    delete_response = client.delete("/api/types/architecture_note", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["deletion_warning"] is True

    snapshot = gateway.get_entry(entry.entry_id)
    assert snapshot.type_id == "architecture_note"
    assert snapshot.type_label == "Architecture"

    clear_resp = client.patch(
        f"/api/entries/{entry.entry_id}",
        json={"taxonomy": {"type": {"clear": True}}},
        headers=headers,
    )
    assert clear_resp.status_code == 200
    cleared = gateway.get_entry(entry.entry_id)
    assert cleared.type_id is None and cleared.type_label is None

    events = cleared.metadata.get("capture_events") or []
    assert events
    assert events[-1]["type"] == "taxonomy.reference.cleared"
    assert events[-1]["data"]["dimension"] == "type"
