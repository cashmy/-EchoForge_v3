"""FastAPI-level tests for taxonomy CRUD endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_taxonomy_service
from backend.app.api.routers import taxonomy
from backend.app.domain.taxonomy import (
    InMemoryTaxonomyRepository,
    TaxonomyKind,
    TaxonomyService,
)
from backend.app.infra.events import EventEmitter
from backend.app.infra.metrics import MetricsClient


class RecordingEmitter(EventEmitter):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def emit(self, topic: str, payload):  # type: ignore[override]
        self.calls.append({"topic": topic, "payload": payload})


class RecordingMetrics(MetricsClient):
    def __init__(self) -> None:
        self.increments: list[tuple[str, int]] = []
        self.gauges: list[tuple[str, int]] = []

    def increment(self, metric: str, value: int = 1) -> None:
        self.increments.append((metric, value))

    def gauge(self, metric: str, value: int) -> None:
        self.gauges.append((metric, value))


def _build_client(service: TaxonomyService) -> TestClient:
    app = FastAPI()
    app.include_router(taxonomy.router)
    app.dependency_overrides[get_taxonomy_service] = lambda: service
    return TestClient(app)


def _build_service(
    *, allow_hard_delete: bool
) -> tuple[
    TaxonomyService, RecordingEmitter, RecordingMetrics, InMemoryTaxonomyRepository
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
    return service, emitter, metrics, repository


def test_create_type_and_list_with_actor_metadata():
    service, emitter, _metrics, _repo = _build_service(allow_hard_delete=True)
    client = _build_client(service)

    headers = {"X-Actor-Id": "tester", "X-Actor-Source": "unit_suite"}
    create_resp = client.post(
        "/api/types",
        json={"id": "project_note", "label": "Project Note"},
        headers=headers,
    )

    assert create_resp.status_code == 201
    list_resp = client.get("/api/types")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["label"] == "Project Note"
    assert emitter.calls
    assert emitter.calls[-1]["topic"] == "taxonomy.type.created"
    payload = emitter.calls[-1]["payload"]
    assert payload["actor_id"] == "tester"
    assert payload["actor_source"] == "unit_suite"


def test_create_type_rejects_invalid_slug():
    service, _emitter, _metrics, _repo = _build_service(allow_hard_delete=True)
    client = _build_client(service)

    resp = client.post(
        "/api/types",
        json={"id": "InvalidSlug", "label": "Bad"},
    )

    assert resp.status_code == 422


def test_delete_type_returns_warning_when_references_exist():
    service, _emitter, _metrics, repository = _build_service(allow_hard_delete=True)
    client = _build_client(service)
    client.post("/api/types", json={"id": "ops", "label": "Ops"})
    repository._store[TaxonomyKind.TYPE]["ops"].referenced_entries = 2

    resp = client.delete("/api/types/ops")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"deletion_warning": True, "referenced_entries": 2}


def test_delete_type_blocked_when_not_allowed():
    service, _emitter, _metrics, _repo = _build_service(allow_hard_delete=False)
    client = _build_client(service)
    client.post("/api/types", json={"id": "ops", "label": "Ops"})

    resp = client.delete("/api/types/ops")

    assert resp.status_code == 405
    detail = resp.json()["detail"]
    assert detail["error_code"] == "EF07-HARD-DELETE-DISABLED"


def test_domain_update_toggle_active_state():
    service, emitter, _metrics, _repo = _build_service(allow_hard_delete=True)
    client = _build_client(service)
    client.post("/api/domains", json={"id": "security", "label": "Security"})

    deactivate = client.patch(
        "/api/domains/security",
        json={"active": False},
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["active"] is False

    reactivate = client.patch(
        "/api/domains/security",
        json={"active": True},
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["active"] is True
    assert any(call["topic"] == "taxonomy.domain.reactivated" for call in emitter.calls)
